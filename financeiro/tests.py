import uuid
from datetime import date, time
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from clientes.models import Cliente, Uf, Liberacao
from contratos.models import Contrato
from notas.models import Nota
from empresa.models import Empresa
from usuario.models import Usuario
from compras.models import Fornecedor
from conta.models import Banco, Conta, Movimento
from conta.services import ContaConflict
from .models import DocReceita, DocDespesa, RecReceita, PagDespesa, FechamentoCaixa, OperacaoBaixa


class FinanceiroAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Empresa.objects.create(cnpj='1', razao='Empresa A')
        cls.other = Empresa.objects.create(cnpj='2', razao='Empresa B')
        cls.user = Usuario.objects.create_user(username='financeiro_test', email='financeiro@example.test', password='test')
        cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='financeiro'))
        bank = Banco.objects.create(codigo='001', nome='Banco')
        cls.account = Conta.objects.create(empresa=cls.company, banco=bank, agencia='001', dv_agencia='0', numeroconta='001', descricao='Conta A')
        cls.foreign_account = Conta.objects.create(empresa=cls.other, banco=bank, agencia='002', dv_agencia='0', numeroconta='002', descricao='Conta B')
        cls.customer = Cliente.objects.create(empresa=cls.company, instituicao='Cliente A', codigolayout=1, codigoentidade=1)
        cls.contract = Contrato.objects.create(empresa=cls.company, cliente=cls.customer)
        cls.note = Nota.objects.create(empresa=cls.company, contrato=cls.contract, numero='001', dt_data_emissao=timezone.now(), competencia=1, exercicio=2026)
        cls.doc = DocReceita.objects.create(empresa=cls.company, cliente=cls.customer, nota=cls.note, numero='R001', descricao='Teste', dt_vencimento='2026-01-01', valor=100, dt_registro='2026-01-01', user_registro=cls.user)
        cls.supplier = Fornecedor.objects.create(empresa=cls.company, instituicao='Fornecedor A')
        cls.expense = DocDespesa.objects.create(empresa=cls.company, fornecedor=cls.supplier, numero='D001', descricao='Despesa', dt_vencimento='2026-01-01', valor=100, dt_registro='2026-01-01', user_registro=cls.user)
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))
    def url(self, resource='receitas', doc=None, action=''):
        return '/financeiro/api/'+resource+'/'+(str(doc.pk)+'/' if doc else '')+action
    def values(self, **changes):
        return {'conta': self.account.pk, 'dt_pagamento': '2026-11-03', 'valor': '40.00', 'idempotencia': str(uuid.uuid4()), **changes}
    def post(self, values=None, doc=None, resource='receitas', action='baixar/'):
        return self.client.post(self.url(resource, doc or self.doc, action), values or self.values(), format='json')
    def close(self, day='2026-11-03'):
        return FechamentoCaixa.objects.create(empresa=self.company, conta=self.account, data=day, hora=time(12), user_fechamento=self.user, receitas=0, despesas=0, saldo_anterior=0, saldo=0)

    def test_auth_company_permissions_and_csrf(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url()).status_code, 401)
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.other.pk))
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        reader = Usuario.objects.create_user(username='reader', email='reader@example.test', password='test')
        reader.empresas.add(self.company)
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='financeiro', codename='view_docreceita'))
        self.client.force_authenticate(reader)
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))
        self.assertEqual(self.client.get(self.url()).status_code, 200)
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.client.get(self.url(doc=self.doc, action='baixas/')).status_code, 403)
        client = APIClient(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post(self.url(doc=self.doc, action='baixar/'), self.values(), format='json').status_code, 403)

    def test_partial_settlement_sum_note_date_and_single_reverse(self):
        first = self.post(); self.assertEqual(first.status_code, 201, first.data)
        self.doc.refresh_from_db(); self.note.refresh_from_db()
        self.assertEqual(self.doc.valor_recebido, Decimal('40')); self.assertEqual(self.doc.situacao, 'A')
        self.assertIsNone(self.note.dt_data_pagamento); self.assertFalse(Liberacao.objects.exists())
        second = self.post(self.values(valor='60.00')); self.assertEqual(second.status_code, 201, second.data)
        self.doc.refresh_from_db(); self.note.refresh_from_db()
        self.assertEqual(self.doc.valor_recebido, Decimal('100')); self.assertEqual(self.doc.situacao, 'R')
        self.assertEqual(self.note.dt_data_pagamento, date(2026,11,3)); self.assertEqual(Movimento.objects.count(), 2)
        response = self.post({'baixa': first.data['id']}, action='estornar/'); self.assertEqual(response.status_code, 200, response.data)
        self.doc.refresh_from_db(); self.note.refresh_from_db()
        self.assertEqual(self.doc.valor_recebido, Decimal('60')); self.assertEqual(self.doc.situacao, 'A')
        self.assertIsNone(self.note.dt_data_pagamento); self.assertEqual(RecReceita.objects.count(), 1); self.assertEqual(Movimento.objects.count(), 1)
        self.assertTrue(Liberacao.objects.exists())

    def test_payment_amount_cheque_and_movement(self):
        bad = self.post(self.values(forma_pagamento='C'), self.expense, 'despesas'); self.assertEqual(bad.status_code, 400)
        response = self.post(self.values(valor='100.00', forma_pagamento='C', numero_cheque='000123'), self.expense, 'despesas')
        self.assertEqual(response.status_code, 201, response.data)
        self.expense.refresh_from_db(); move = Movimento.objects.get()
        self.assertEqual(self.expense.valor_pago, Decimal('100')); self.assertEqual(self.expense.situacao, 'P')
        self.assertEqual(move.nr_documento, '000123'); self.assertEqual(move.tipo_documento, 'CHE'); self.assertEqual(move.tipo_movimento, 'D')

    def test_idempotency_changed_payload_and_replay_after_reverse(self):
        values = self.values()
        first = self.post(values); second = self.post(values)
        self.assertEqual(second.status_code, 200, second.data); self.assertEqual(second.data['id'], first.data['id'])
        self.assertEqual(RecReceita.objects.count(), 1); self.assertEqual(OperacaoBaixa.objects.count(), 1)
        self.assertEqual(self.post({**values, 'valor': '41.00'}).status_code, 409)
        self.post({'baixa': first.data['id']}, action='estornar/')
        self.assertEqual(self.post(values).status_code, 409); self.assertFalse(RecReceita.objects.exists())

    def test_invalid_overpayment_foreign_account_and_decimal_precision(self):
        for changes in ({'valor':'101.00'}, {'valor':'0'}, {'valor':'-1'}, {'valor':'1.001'}, {'conta':self.foreign_account.pk}, {'idempotencia':'bad'}):
            response = self.post(self.values(**changes)); self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(RecReceita.objects.exists()); self.assertFalse(Movimento.objects.exists())

    def test_closed_period_create_and_reverse_preserve_all_data(self):
        response = self.post(); self.close()
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.post({'baixa':response.data['id']}, action='estornar/').status_code, 409)
        self.assertEqual(Movimento.objects.count(), 1); self.assertEqual(RecReceita.objects.count(), 1)

    def test_ledger_failure_rolls_back_receipt_summary_release_and_key(self):
        with patch('conta.services.sincronizar_pagamento', side_effect=ContaConflict('Falha simulada')):
            response = self.post(self.values(valor='100.00'))
        self.assertEqual(response.status_code, 409)
        self.doc.refresh_from_db(); self.note.refresh_from_db()
        self.assertEqual(self.doc.valor_recebido, 0); self.assertIsNone(self.note.dt_data_pagamento)
        self.assertFalse(RecReceita.objects.exists()); self.assertFalse(OperacaoBaixa.objects.exists()); self.assertFalse(Liberacao.objects.exists())

    def test_inconsistent_legacy_payment_cannot_be_reversed_or_extended(self):
        payment = RecReceita.objects.create(receita=self.doc, conta=self.account, dt_pagamento='2026-11-03', valor=10, user_registro=self.user)
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(self.post({'baixa':payment.pk}, action='estornar/').status_code, 409)
        self.assertTrue(RecReceita.objects.filter(pk=payment.pk).exists())

    def test_readonly_totals_actor_and_document_update_lock(self):
        response = self.client.patch(self.url(doc=self.doc), {'valor_recebido':'999', 'situacao':'R', 'empresa':self.other.pk, 'user_registro':999, 'descricao':'Editado'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.doc.refresh_from_db(); self.assertEqual(self.doc.valor_recebido, 0); self.assertEqual(self.doc.empresa_id,self.company.pk)
        self.post()
        self.assertEqual(self.client.patch(self.url(doc=self.doc), {'valor':'200'}, format='json').status_code,409)
        self.assertEqual(self.client.delete(self.url(doc=self.doc)).status_code,409)

    def test_expense_create_scope_zero_values_and_delete(self):
        values = {'fornecedor':self.supplier.pk,'numero':'NEW','descricao':'Nova','valor':'12.34','dt_vencimento':'2026-12-31'}
        response = self.client.post(self.url('despesas'),values,format='json'); self.assertEqual(response.status_code,201,response.data)
        doc = DocDespesa.objects.get(pk=response.data['id']); self.assertEqual(doc.user_registro_id,self.user.pk)
        foreign = Fornecedor.objects.create(empresa=self.other,instituicao='Foreign')
        self.assertEqual(self.client.post(self.url('despesas'),{**values,'fornecedor':foreign.pk},format='json').status_code,400)
        self.assertEqual(self.client.delete(self.url('despesas',doc)).status_code,204)

    def test_receipt_creation_note_customer_validation_and_duplicate(self):
        values = {'cliente':self.customer.pk,'nota':self.note.pk,'numero':'NEW','descricao':'Nova','valor':'100','dt_vencimento':'2026-12-31'}
        response = self.client.post(self.url(),values,format='json'); self.assertEqual(response.status_code,409,response.data)
        note = Nota.objects.create(empresa=self.company,contrato=self.contract,numero='002',dt_data_emissao=timezone.now(),competencia=2,exercicio=2026)
        response = self.client.post(self.url(),{**values,'nota':note.pk},format='json'); self.assertEqual(response.status_code,201,response.data)

    def test_uf_scope_also_applies_to_options_and_actions(self):
        uf = Uf.objects.create(sigla='CE',descricao='Ceará'); self.user.uf=uf; self.user.save()
        self.assertEqual(self.client.get(self.url()).data['count'],0)
        self.assertEqual(self.post().status_code,404)
        self.assertEqual(self.client.get('/financeiro/api/opcoes/?tipo=clientes').data['count'],0)

    def test_reports_use_actual_receipts_and_no_join_multiplication(self):
        self.post(); self.post(self.values(valor='20.00'))
        self.doc.valor_recebido=999; self.doc.situacao='R'; self.doc.save()
        response=self.client.get(self.url(action='relatorio/'),{'situacao':'aberto','page_size':1,'pagamento_inicial':'2026-11-01','pagamento_final':'2026-11-30'})
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['count'],1); self.assertEqual(Decimal(response.data['saldo_total']),40)
        self.assertEqual(response.data['results'][0]['situacao_atual'],'Vencido')
        self.assertEqual(self.client.get(self.url(),{'dt_inicial':'2026-01-01'}).status_code,400)

    def test_duplicate_month_end_and_company_actor(self):
        response=self.post({'quantidade':3,'primeiro_vencimento':'2028-01-31'},self.expense,'despesas','duplicar/')
        self.assertEqual(response.status_code,201,response.data)
        docs=list(DocDespesa.objects.filter(pk__in=response.data['ids']).order_by('dt_vencimento'))
        self.assertEqual([doc.dt_vencimento.isoformat() for doc in docs],['2028-01-31','2028-02-29','2028-03-31'])
        self.assertTrue(all(doc.valor_pago==0 and doc.user_registro_id==self.user.pk for doc in docs))

    def test_closing_api_balances_and_reopen_latest_only(self):
        self.post()
        response=self.client.post(self.url('fechamentos'),{'conta':self.account.pk,'dt_inicial':'2026-11-03','dt_final':'2026-11-04'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        first,last=list(FechamentoCaixa.objects.order_by('data'))
        self.assertEqual(last.saldo,Decimal('40'))
        self.assertEqual(self.client.post(self.url('fechamentos',first,'reabrir/')).status_code,409)
        self.assertEqual(self.client.post(self.url('fechamentos',last,'reabrir/')).status_code,200)
        self.assertEqual(self.client.post(self.url('fechamentos',first,'reabrir/')).status_code,200)

    def preview(self, content='data;valor;documento;historico\n03/11/2026;40,00;DOC1;Teste\n'):
        return self.client.post(self.url(action='previsualizar/'), {'extrato':SimpleUploadedFile('extrato.csv',content.encode(),content_type='text/csv')},format='multipart')
    def test_reconciliation_preview_signature_atomicity_and_idempotency(self):
        preview=self.preview(); self.assertEqual(preview.status_code,200,preview.data); self.assertFalse(RecReceita.objects.exists())
        token=preview.data['results'][0]['token']; payload={'conta':self.account.pk,'itens':[{'token':token,'receita':self.doc.pk}]}
        response=self.client.post(self.url(action='conciliar/'),payload,format='json'); self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.post(self.url(action='conciliar/'),payload,format='json').status_code,200)
        self.assertEqual(RecReceita.objects.count(),1)
        payload['itens'][0]['token']+='tamper'
        self.assertEqual(self.client.post(self.url(action='conciliar/'),payload,format='json').status_code,400)

    def test_batch_overpayment_rolls_back_every_line(self):
        preview=self.preview('data;valor;documento;historico\n03/11/2026;40,00;DOC1;Teste\n03/11/2026;80,00;DOC2;Teste\n')
        payload={'conta':self.account.pk,'itens':[{'token':r['token'],'receita':self.doc.pk} for r in preview.data['results']]}
        response=self.client.post(self.url(action='conciliar/'),payload,format='json'); self.assertEqual(response.status_code,400,response.data)
        self.assertFalse(RecReceita.objects.exists()); self.assertFalse(Movimento.objects.exists()); self.assertFalse(OperacaoBaixa.objects.exists())

    def test_preview_rejects_bad_values_and_foreign_company_token(self):
        self.assertEqual(self.preview('bad;header\n').status_code,400)
        self.assertEqual(self.preview('data;valor;documento\n03/11/2026;-10,00;X\n').status_code,400)
        preview=self.preview(); self.user.empresas.add(self.other); self.client.credentials(HTTP_X_EMPRESA_ID=str(self.other.pk))
        response=self.client.post(self.url(action='conciliar/'),{'conta':self.foreign_account.pk,'itens':[{'token':preview.data['results'][0]['token'],'receita':self.doc.pk}]},format='json')
        self.assertEqual(response.status_code,400)

    def test_legacy_routes_redirect_without_mutating(self):
        self.assertEqual(self.client.get('/financeiro/lista_receitas/').url,'/clientes/app/receitas')
        response=self.client.post(f'/financeiro/extorna_receita/{self.doc.pk}/')
        self.assertEqual(response.status_code,302); self.assertTrue(DocReceita.objects.filter(pk=self.doc.pk).exists())
