from datetime import date, time
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from clientes.models import Cliente
from contratos.models import Contrato
from notas.models import Nota
from empresa.models import Empresa
from usuario.models import Usuario
from contabil.models import PlanoContas
from financeiro.models import FechamentoCaixa, DocReceita, RecReceita
from .models import Banco, Conta, Movimento, Transferencia, AddMovimento
from .services import ContaConflict


class ContaAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Empresa.objects.create(cnpj='1', razao='Empresa A')
        cls.other = Empresa.objects.create(cnpj='2', razao='Empresa B')
        cls.bank = Banco.objects.create(codigo='001', nome='Banco A')
        cls.plan = PlanoContas.objects.create(empresa=cls.company, conta='1.1', descricao='Disponível')
        cls.foreign_plan = PlanoContas.objects.create(empresa=cls.other, conta='1.1', descricao='Plano B')
        cls.user = Usuario.objects.create_user(username='contas_test', email='contas@example.test', password='test')
        cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='conta'))
        cls.a = Conta.objects.create(empresa=cls.company, banco=cls.bank, agencia='001', dv_agencia='X', numeroconta='001', dv_conta='1', descricao='Origem')
        cls.b = Conta.objects.create(empresa=cls.company, banco=cls.bank, agencia='001', dv_agencia='X', numeroconta='002', dv_conta='1', descricao='Destino')
        cls.foreign_account = Conta.objects.create(empresa=cls.other, banco=cls.bank, agencia='002', dv_agencia='0', numeroconta='003', descricao='Conta B')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(self.user)), HTTP_X_EMPRESA_ID=str(self.company.pk))
        self.base = '/conta/api/'

    def transfer(self, **changes):
        return {**{'conta_origem': self.a.pk, 'conta_destino': self.b.pk, 'dt_movimento': '2026-11-03', 'valor': '100.123', 'nr_documento': 'DOC-1', 'historico': 'Transferência local'}, **changes}

    def movement(self, **changes):
        return {**{'conta': self.a.pk, 'tipo_documento': 'OUT', 'tipo_movimento': 'C', 'dt_movimento': '2026-11-03', 'valor': '10.123', 'nr_documento': 'MOV-1', 'historico': 'Teste'}, **changes}

    def closure(self, account=None, day='2026-11-03', amount='0'):
        return FechamentoCaixa.objects.create(empresa=self.company, conta=account or self.a, data=day, hora=time(12),
            user_fechamento=self.user, receitas=0, despesas=0, saldo=amount, saldo_anterior=0)

    def post(self, resource, data):
        return self.client.post(self.base + resource + '/', data, format='json')

    def test_auth_company_and_readonly_permissions(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.base + 'contas/').status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid')
        self.assertEqual(self.client.get(self.base + 'contas/').status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(self.user)))
        self.assertEqual(self.client.get(self.base + 'bancos/').status_code, 400)
        self.assertEqual(self.client.get(self.base + 'contas/', {'empresa': self.other.pk}).status_code, 403)

    def test_banks_global_catalog_and_duplicate_validation(self):
        self.assertEqual(self.client.get(self.base + 'bancos/').data['count'], 1)
        for data in ({'codigo': '001', 'nome': 'Novo'}, {'codigo': '2', 'nome': 'Banco A'}, {'codigo': '2', 'nome': ''}):
            self.assertEqual(self.post('bancos', data).status_code, 400)
        created = self.post('bancos', {'codigo': '999', 'nome': 'Novo banco'})
        self.assertEqual(created.status_code, 201, created.data)
        path = self.base + f'bancos/{created.data["id"]}/'
        self.assertEqual(self.client.patch(path, {'nome': 'Editado'}, format='json').status_code, 200)
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.delete(self.base + f'bancos/{self.bank.pk}/').status_code, 409)

    def test_accounts_scoped_and_foreign_plan_rejected(self):
        response = self.client.get(self.base + 'contas/')
        self.assertEqual(response.data['count'], 2)
        path = self.base + f'contas/{self.foreign_account.pk}/'
        for method in ('get', 'patch', 'delete'):
            self.assertEqual(getattr(self.client, method)(path, {}, format='json').status_code, 404)
        data = {'empresa': self.other.pk, 'banco': self.bank.pk, 'agencia': '0001', 'dv_agencia': 'X', 'numeroconta': '000007', 'dv_conta': '0', 'descricao': 'Nova', 'conta_contabil': self.plan.pk}
        created = self.post('contas', data)
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data['empresa'], self.company.pk)
        self.assertEqual(created.data['numeroconta'], '000007')
        data['conta_contabil'] = self.foreign_plan.pk
        self.assertEqual(self.post('contas', data).status_code, 400)
        data['conta_contabil'] = self.plan.pk
        self.assertEqual(self.post('contas', data).status_code, 400)
        path = self.base + f'contas/{created.data["id"]}/'
        self.assertEqual(self.client.patch(path, {'descricao': 'Alterada'}, format='json').status_code, 200)
        self.assertEqual(self.client.delete(path).status_code, 204)

    def test_manual_movement_crud_actor_and_decimal_precision(self):
        response = self.post('movimentos', self.movement(empresa=self.other.pk, usuario=999, receita=999, despesa=999, transferencia=999))
        self.assertEqual(response.status_code, 201, response.data)
        obj = Movimento.objects.get(pk=response.data['id'])
        self.assertEqual(obj.empresa_id, self.company.pk)
        self.assertEqual(obj.usuario_id, self.user.pk)
        self.assertIsNone(obj.receita_id)
        self.assertEqual(obj.valor, Decimal('10.123'))
        path = self.base + f'movimentos/{obj.pk}/'
        updated = self.client.patch(path, {'valor': '20.456', 'historico': ''}, format='json')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data['valor'], '20.456')
        self.assertEqual(self.client.delete(path).status_code, 204)

    def test_invalid_movements_and_foreign_relations(self):
        for changes in ({'valor': '-1'}, {'valor': '0'}, {'valor': '0.0001'}, {'conta': self.foreign_account.pk}, {'tipo_documento': 'TRA'}, {'tipo_movimento': 'X'}):
            self.assertEqual(self.post('movimentos', self.movement(**changes)).status_code, 400, changes)
        self.assertEqual(Movimento.objects.count(), 0)

    def test_transfer_atomic_pair_and_same_document_is_not_identity(self):
        records = [self.post('transferencias', self.transfer()) for _ in range(2)]
        for response in records:
            self.assertEqual(response.status_code, 201, response.data)
        first, second = [Transferencia.objects.get(pk=response.data['id']) for response in records]
        self.assertEqual(first.transferencia.count(), 2)
        self.assertEqual(first.transferencia.get(tipo_movimento='D').conta_id, self.a.pk)
        self.assertEqual(first.transferencia.get(tipo_movimento='C').conta_id, self.b.pk)
        changed = self.client.patch(self.base + f'transferencias/{first.pk}/', {'valor': '200.456', 'nr_documento': 'ALTERADO'}, format='json')
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(list(first.transferencia.values_list('valor', flat=True)), [Decimal('200.456')]*2)
        self.assertEqual(list(second.transferencia.values_list('valor', flat=True)), [Decimal('100.123')]*2)
        second.refresh_from_db()
        self.assertEqual(second.nr_documento, 'DOC-1')
        self.assertEqual(self.client.delete(self.base+f'transferencias/{first.pk}/').status_code, 204)
        self.assertEqual(second.transferencia.count(), 2)
        self.assertEqual(Movimento.objects.count(), 2)

    def test_transfer_rejects_same_account_foreign_and_invalid_values(self):
        for changes in ({'conta_destino': self.a.pk}, {'conta_destino': self.foreign_account.pk}, {'valor': '0'}, {'valor': '0.0001'}):
            self.assertEqual(self.post('transferencias', self.transfer(**changes)).status_code, 400)
        self.assertEqual(Transferencia.objects.count(), 0)
        self.assertEqual(Movimento.objects.count(), 0)

    def test_failed_second_leg_rolls_back_parent_and_first_leg(self):
        save = Movimento.save
        def fail_on_credit(instance, *args, **kwargs):
            if instance.tipo_movimento == 'C':
                raise RuntimeError('Falha simulada no segundo movimento')
            return save(instance, *args, **kwargs)
        with patch.object(Movimento, 'save', fail_on_credit), self.assertRaises(RuntimeError):
            self.post('transferencias', self.transfer())
        self.assertFalse(Transferencia.objects.exists())
        self.assertFalse(Movimento.objects.exists())

    def test_closed_destination_blocks_creation(self):
        self.closure(self.b)
        self.assertEqual(self.post('transferencias', self.transfer()).status_code, 409)
        self.assertFalse(Transferencia.objects.exists())
        self.assertFalse(Movimento.objects.exists())

    def test_closed_original_period_blocks_moving_date_out_and_deleting(self):
        response = self.post('movimentos', self.movement())
        path = self.base + f'movimentos/{response.data["id"]}/'
        self.closure()
        self.assertEqual(self.client.patch(path, {'dt_movimento': '2026-11-04', 'conta': self.b.pk}, format='json').status_code, 409)
        self.assertEqual(self.client.delete(path).status_code, 409)
        self.assertEqual(self.post('movimentos', self.movement(dt_movimento='2026-11-02')).status_code, 409)
        self.assertEqual(self.post('movimentos', self.movement(dt_movimento='2026-11-04')).status_code, 201)

    def test_transfer_closed_old_destination_blocks_edit_delete(self):
        response = self.post('transferencias', self.transfer())
        self.closure(self.b)
        path = self.base + f'transferencias/{response.data["id"]}/'
        self.assertEqual(self.client.patch(path, {'dt_movimento': '2026-11-04'}, format='json').status_code, 409)
        self.assertEqual(self.client.delete(path).status_code, 409)
        self.assertEqual(Movimento.objects.count(), 2)

    def test_transfer_legs_are_protected_from_individual_edits(self):
        response = self.post('transferencias', self.transfer())
        transfer = Transferencia.objects.get(pk=response.data['id'])
        leg = transfer.transferencia.first()
        path = self.base+f'movimentos/{leg.pk}/'
        self.assertFalse(self.client.get(path).data['editavel'])
        self.assertEqual(self.client.patch(path, {'valor': '1'}, format='json').status_code, 409)
        self.assertEqual(self.client.delete(path).status_code, 409)

    def test_inconsistent_legacy_pairs_require_reconciliation(self):
        response = self.post('transferencias', self.transfer())
        transfer = Transferencia.objects.get(pk=response.data['id'])
        transfer.transferencia.filter(tipo_movimento='C').delete()
        path = self.base+f'transferencias/{transfer.pk}/'
        self.assertEqual(self.client.patch(path, {'valor': '1'}, format='json').status_code, 409)
        self.assertEqual(self.client.delete(path).status_code, 409)
        transfer.refresh_from_db()
        self.assertEqual(transfer.valor, Decimal('100.123'))
        self.assertEqual(transfer.transferencia.count(), 1)

    def receipt(self, account, number='MESMO'):
        customer = Cliente.objects.create(empresa=account.empresa, instituicao='Cliente')
        contract = Contrato.objects.create(empresa=account.empresa, cliente=customer)
        note = Nota.objects.create(empresa=account.empresa, contrato=contract, dt_data_emissao=timezone.now(), competencia=11, exercicio=2026)
        doc = DocReceita.objects.create(empresa=account.empresa, cliente=customer, nota=note, numero=number, descricao='Descrição', dt_vencimento='2026-11-03', valor=10, dt_registro='2026-11-03', user_registro=self.user)
        return RecReceita.objects.create(receita=doc, conta=account, dt_pagamento='2026-11-03', valor=10, user_registro=self.user)

    def test_legacy_payment_sync_uses_payment_fk_and_preserves_other_companies(self):
        first = self.receipt(self.a)
        other = self.receipt(self.foreign_account)
        a = AddMovimento(first, 'c')
        b = AddMovimento(other, 'c')
        self.assertNotEqual(a.pk, b.pk)
        self.assertEqual(AddMovimento(first, 'c').pk, a.pk)
        self.assertEqual(Movimento.objects.count(), 2)
        self.assertEqual(self.client.get(self.base+'movimentos/').data['count'], 1)
        path = self.base+f'movimentos/{a.pk}/'
        self.assertEqual(self.client.delete(path).status_code, 409)
        self.assertEqual(self.client.patch(path, {'valor': '1'}, format='json').status_code, 409)
        self.assertEqual(self.client.get(self.base+f'movimentos/{b.pk}/').status_code, 404)

    def test_payment_sync_rejects_foreign_account_and_closed_period(self):
        receipt = self.receipt(self.a)
        receipt.conta = self.foreign_account; receipt.save()
        with self.assertRaises(ContaConflict):
            AddMovimento(receipt, 'c')
        self.assertFalse(Movimento.objects.exists())
        receipt.conta = self.a; receipt.save()
        self.closure()
        with self.assertRaises(ContaConflict):
            AddMovimento(receipt, 'c')
        self.assertFalse(Movimento.objects.exists())

    def test_reports_totals_and_filters_use_all_pages_and_company(self):
        for values in (self.movement(valor='1.001'), self.movement(tipo_movimento='D', valor='0.100', tipo_documento='CHE')):
            self.assertEqual(self.post('movimentos', values).status_code, 201)
        response = self.client.get(self.base+'movimentos/relatorio/', {'page_size': 1})
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(Decimal(response.data['creditos']), Decimal('1.001'))
        self.assertEqual(Decimal(response.data['saldo_periodo']), Decimal('0.901'))
        self.assertEqual(self.client.get(self.base+'movimentos/', {'tipo_documento': 'CHE'}).data['count'], 1)
        for values in ({'dt_inicial': '2026-01-01'}, {'dt_inicial': '2026-02-01', 'dt_final': '2026-01-01'}, {'tipo_movimento': 'X'}, {'conta': 'x'}):
            self.assertEqual(self.client.get(self.base+'movimentos/', values).status_code, 400)
        self.post('transferencias', self.transfer())
        report = self.client.get(self.base+'transferencias/relatorio/')
        self.assertEqual(report.data['valor_total'], '100.123')

    def test_statement_uses_latest_previous_closure_and_gap_movements(self):
        self.closure(day='2026-01-01', amount='10.0000')
        for day, direction, amount in [('2026-01-03', 'C', '2.001'), ('2026-01-04', 'D', '1.000'), ('2026-01-05', 'C', '4.001'), ('2026-01-06', 'D', '3.000')]:
            self.assertEqual(self.post('movimentos', self.movement(dt_movimento=day, tipo_movimento=direction, valor=amount)).status_code, 201)
        response = self.client.get(self.base+'movimentos/extrato/', {'conta': self.a.pk, 'dt_inicial': '2026-01-05', 'dt_final': '2026-01-06', 'page_size': 1})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(response.data['saldo_anterior']), Decimal('11.0010'))
        self.assertEqual(Decimal(response.data['saldo_final']), Decimal('12.0020'))
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(self.client.get(self.base+'movimentos/extrato/', {'conta': self.foreign_account.pk, 'dt_inicial': '2026-01-05', 'dt_final': '2026-01-06'}).status_code, 403)

    def test_read_only_permissions_options_legacy_and_csrf(self):
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='conta', codename__startswith='view_'))
        for resource in ('bancos', 'contas', 'movimentos', 'transferencias'):
            self.assertEqual(self.client.get(self.base+resource+'/').status_code, 200)
            self.assertEqual(self.post(resource, {}).status_code, 403)
        for kind in ('bancos', 'planos', 'contas'):
            response = self.client.get(self.base+'opcoes/', {'tipo': kind})
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.get('/conta/list_mov/').url, '/clientes/app/movimentos')
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.base+'movimentos/', self.movement(), format='json').status_code, 403)

    def test_account_delete_protects_linked_movements(self):
        self.post('movimentos', self.movement())
        self.assertEqual(self.client.delete(self.base+f'contas/{self.a.pk}/').status_code, 409)
        self.assertTrue(Conta.objects.filter(pk=self.a.pk).exists())

    def test_financial_legacy_routes_require_review_in_react(self):
        response = self.client.get('/financeiro/lista_receitas/')
        self.assertEqual(response.url, '/clientes/app/receitas')
        response = self.client.post('/financeiro/baixar_confirma/', {'conta': self.a.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Movimento.objects.exists())

    def test_pending_transfer_filter_and_readonly_audit(self):
        from io import StringIO
        from django.core.management import call_command
        first = self.post('transferencias', self.transfer()).data['id']
        second = self.post('transferencias', self.transfer()).data['id']
        Movimento.objects.filter(transferencia_id=second, tipo_movimento='C').delete()
        for state, ids in [('pendente', [second]), ('consistente', [first])]:
            response = self.client.get(self.base+'transferencias/', {'integridade': state})
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual([r['id'] for r in response.data['results']], ids)
        response = self.client.get(self.base+'transferencias/relatorio/', {'integridade': 'pendente'})
        self.assertEqual(Decimal(response.data['valor_total']), Decimal('100.123'))
        self.assertFalse(response.data['results'][0]['editavel'])
        output = StringIO()
        call_command('auditar_transferencias', stdout=output)
        self.assertIn('conciliação necessária: 1', output.getvalue())
        self.assertEqual(Transferencia.objects.count(), 2)
        self.assertEqual(Movimento.objects.count(), 3)

    def test_failed_transfer_update_preserves_parent_and_both_legs(self):
        response = self.post('transferencias', self.transfer())
        transfer = Transferencia.objects.get(pk=response.data['id'])
        save = Movimento.save
        def fail_on_credit(instance, *args, **kwargs):
            if instance.tipo_movimento == 'C':
                raise RuntimeError('Falha simulada')
            return save(instance, *args, **kwargs)
        with patch.object(Movimento, 'save', fail_on_credit), self.assertRaises(RuntimeError):
            self.client.patch(self.base+f'transferencias/{transfer.pk}/', {'valor': '999'}, format='json')
        transfer.refresh_from_db()
        self.assertEqual(transfer.valor, Decimal('100.123'))
        self.assertEqual(list(transfer.transferencia.values_list('valor', flat=True)), [Decimal('100.123')]*2)

    def test_legacy_expense_payment_sync_preserves_cheque_and_fk(self):
        from compras.models import Fornecedor
        from financeiro.models import DocDespesa, PagDespesa
        supplier = Fornecedor.objects.create(empresa=self.company, instituicao='Fornecedor teste')
        document = DocDespesa.objects.create(empresa=self.company, fornecedor=supplier, numero='MESMO', descricao='Despesa',
            dt_vencimento='2026-11-03', valor='20.10', dt_registro='2026-11-03', user_registro=self.user)
        payment = PagDespesa.objects.create(despesa=document, conta=self.a, forma_pagamento='C', numero_cheque='000123',
            dt_pagamento='2026-11-03', valor='20.10', user_registro=self.user)
        movement = AddMovimento(payment, 'd')
        self.assertEqual(movement.despesa_id, payment.pk)
        self.assertEqual(movement.tipo_documento, 'CHE')
        self.assertEqual(movement.tipo_movimento, 'D')
        self.assertEqual(movement.nr_documento, '000123')
        self.assertEqual(movement.valor, Decimal('20.100'))
        self.assertEqual(AddMovimento(payment, 'd').pk, movement.pk)
        self.assertEqual(self.client.get(self.base+'movimentos/', {'tipo_documento': 'CHE'}).data['count'], 1)
