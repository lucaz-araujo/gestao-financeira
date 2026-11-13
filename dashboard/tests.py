from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from clientes.models import Cliente, Parceiro, Uf
from contratos.models import Contrato
from empresa.models import Empresa
from financeiro.models import DocReceita, RecReceita
from notas.models import Nota
from usuario.models import Usuario

TODAY = date(2026, 11, 15)
PERMISSIONS = ['clientes.view_cliente', 'clientes.view_parceiro', 'notas.view_nota', 'contratos.view_contrato', 'financeiro.view_docreceita']


class DashboardAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Empresa.objects.create(cnpj='1', razao='Empresa Alfa')
        cls.other = Empresa.objects.create(cnpj='2', razao='Empresa Beta')
        cls.empty = Empresa.objects.create(cnpj='3', razao='Empresa Vazia')
        cls.uf = Uf.objects.create(sigla='CE', descricao='Ceará')
        cls.other_uf = Uf.objects.create(sigla='PI', descricao='Piauí')
        cls.partner = Parceiro.objects.create(empresa=cls.company, instituicao='Parceiro Alfa', uf=cls.uf)
        cls.foreign_partner = Parceiro.objects.create(empresa=cls.other, instituicao='Parceiro Beta', uf=cls.uf)
        cls.customer = Cliente.objects.create(empresa=cls.company, instituicao='Cliente Alfa', uf=cls.uf, parceiro=cls.partner)
        cls.second = Cliente.objects.create(empresa=cls.company, instituicao='Cliente Inativo', uf=cls.uf, ativo=False)
        cls.hidden = Cliente.objects.create(empresa=cls.company, instituicao='Cliente PI', uf=cls.other_uf)
        cls.foreign = Cliente.objects.create(empresa=cls.other, instituicao='Cliente Beta', uf=cls.uf)
        cls.user = Usuario.objects.create_user(username='dashboard_test', email='dashboard@example.test', password='Dashboard-test-918!', ultimo_mes=11, ultimo_ano=2026)
        cls.user.empresas.add(cls.company, cls.other, cls.empty)
        cls.user.user_permissions.set(Permission.objects.filter(codename__in=[value.split('.')[1] for value in PERMISSIONS]))
        cls.contract = Contrato.objects.create(empresa=cls.company, cliente=cls.customer, numero='CON-ALFA', exercicio=2026, ativo=True, dt_data_final=TODAY + timedelta(days=7))
        cls.hidden_contract = Contrato.objects.create(empresa=cls.company, cliente=cls.hidden, numero='CON-PI', exercicio=2026, dt_data_final=TODAY)
        cls.foreign_contract = Contrato.objects.create(empresa=cls.other, cliente=cls.foreign, numero='CON-BETA', exercicio=2026, dt_data_final=TODAY)
        cls.mismatch = Contrato.objects.create(empresa=cls.company, cliente=cls.foreign, numero='CON-INVALIDO', exercicio=2026, dt_data_final=TODAY)
        def note(contract, company, **changes):
            return Nota.objects.create(contrato=contract, empresa=company, dt_data_emissao=timezone.now(), competencia=11, exercicio=2026, valor_bruto=100, valor_liquido=100, **changes)
        cls.note = note(cls.contract, cls.company, numero='ALFA')
        cls.paid_note = note(cls.contract, cls.company, numero='PAGA', dt_data_pagamento=TODAY)
        cls.hidden_note = note(cls.hidden_contract, cls.company)
        cls.foreign_note = note(cls.foreign_contract, cls.other)
        cls.invalid_note = note(cls.foreign_contract, cls.company)
        cls.doc = DocReceita.objects.create(empresa=cls.company, cliente=cls.customer, nota=cls.note, numero='REC-ALFA', descricao='Teste', dt_vencimento=date(2026,11,1), valor=100, valor_recebido=99, dt_registro=TODAY, user_registro=cls.user)
        RecReceita.objects.create(receita=cls.doc, valor=Decimal('30.10'), dt_pagamento=TODAY, user_registro=cls.user)
        RecReceita.objects.create(receita=cls.doc, valor=Decimal('19.90'), dt_pagamento=TODAY, user_registro=cls.user)

    def setUp(self):
        self.enterContext(patch('dashboard.services.timezone.localdate', return_value=TODAY))
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))

    def summary(self, **params):
        return self.client.get('/dashboard/api/resumo/', {'mes': 11, 'ano': 2026, **params})

    def permissions(self, *values):
        self.user.user_permissions.set(Permission.objects.filter(codename__in=[value.split('.')[1] for value in values]))
        self.user = Usuario.objects.get(pk=self.user.pk)
        self.client.force_authenticate(self.user)

    def test_authentication_and_company_membership_are_required(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.summary().status_code, 401)
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_EMPRESA_ID='999999')
        self.assertEqual(self.summary().status_code, 403)
        self.client.credentials(HTTP_X_EMPRESA_ID='invalid')
        self.assertEqual(self.summary().status_code, 400)
        self.client.credentials()
        self.assertEqual(self.summary().status_code, 400)
        self.assertEqual(self.summary(empresa=self.company.pk).status_code, 200)

    def test_company_and_uf_scope_covers_all_sections_and_inconsistent_links(self):
        self.user.uf = self.uf; self.user.save(update_fields=['uf'])
        response = self.summary(); self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['clientes'], {'total': 2, 'ativos': 1})
        self.assertEqual(response.data['notas']['total'], 2)
        self.assertEqual([row['numero'] for row in response.data['alertas']['results']], ['CON-ALFA'])
        self.assertEqual(response.data['parceiros']['results'][0]['percentual'], '50.00')
        self.assertNotIn('CON-BETA', str(response.data))
        self.assertNotIn('Cliente PI', str(response.data))
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_each_section_requires_its_real_model_permission(self):
        for permission, section in [('notas.view_nota','notas'), ('financeiro.view_docreceita','receitas'), ('contratos.view_contrato','alertas'), ('clientes.view_cliente','clientes')]:
            self.permissions(permission)
            response = self.summary(); self.assertEqual(response.status_code, 200, response.data)
            for key in ('clientes','notas','receitas','alertas','parceiros'):
                if key == section: self.assertIsNotNone(response.data[key])
                else: self.assertIsNone(response.data[key])
        self.permissions('clientes.view_parceiro')
        self.assertEqual(self.summary().status_code, 403)

    def test_financial_totals_use_real_partial_receipts_and_reversal(self):
        data = self.summary().data['receitas']
        self.assertEqual(data['valor_total'], '100.00'); self.assertEqual(data['recebido'], '50.00')
        self.assertEqual(data['saldo'], '50.00'); self.assertEqual(data['vencido'], '50.00')
        self.assertEqual(data['vencem_em_10_dias'], '0.00')
        RecReceita.objects.filter(receita=self.doc, valor=Decimal('19.90')).delete()
        self.assertEqual(self.summary().data['receitas']['saldo'], '69.90')

    def test_no_duplicate_document_totals_when_there_are_multiple_receipts(self):
        RecReceita.objects.create(receita=self.doc, valor=50, dt_pagamento=TODAY, user_registro=self.user)
        data = self.summary().data['receitas']
        self.assertEqual(data['documentos'], 1); self.assertEqual(data['valor_total'], '100.00')
        self.assertEqual(data['recebido'], '100.00'); self.assertEqual(data['vencido'], '0.00')

    def test_financial_scope_excludes_other_companies_and_ufs(self):
        self.user.uf=self.uf;self.user.save(update_fields=['uf'])
        for company,customer,note in [(self.other,self.foreign,self.foreign_note),(self.company,self.hidden,self.hidden_note)]:
            DocReceita.objects.create(empresa=company,cliente=customer,nota=note,numero='HIDDEN',descricao='Não autorizado',dt_vencimento=TODAY,valor=900,dt_registro=TODAY,user_registro=self.user)
        data=self.summary().data['receitas']
        self.assertEqual(data['documentos'],1);self.assertEqual(data['valor_total'],'100.00');self.assertEqual(data['saldo'],'50.00')

    def test_annual_series_uses_fiscal_competence_not_emission_date_and_fills_empty_months(self):
        Nota.objects.filter(pk=self.note.pk).update(competencia=2)
        data = self.summary().data['notas']
        self.assertEqual(data['total'], 2)  # one CE paid + one PI, no UF restriction
        self.assertEqual(len(data['mensal']), 12)
        self.assertEqual(data['mensal'][0]['cadastradas'], 0)
        self.assertEqual(data['mensal'][1]['cadastradas'], 1)
        self.assertEqual(data['mensal'][10]['com_pagamento_registrado'], 1)

    def test_empty_company_has_zero_totals_and_no_partner_division_error(self):
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.empty.pk))
        data = self.summary().data
        self.assertEqual(data['clientes']['total'], 0); self.assertEqual(data['receitas']['saldo'], '0.00')
        self.assertEqual(data['parceiros']['results'], []); self.assertEqual(data['alertas']['count'], 0)

    def test_alerts_are_active_scoped_paginated_and_limited_to_window(self):
        for index in range(12):
            Contrato.objects.create(empresa=self.company, cliente=self.customer, numero=f'PAGE-{index}', exercicio=2026, dt_data_final=TODAY)
        Contrato.objects.create(empresa=self.company, cliente=self.customer, numero='INATIVO', exercicio=2026, dt_data_final=TODAY, ativo=False)
        Contrato.objects.create(empresa=self.company, cliente=self.customer, numero='DISTANTE', exercicio=2026, dt_data_final=TODAY+timedelta(days=31))
        first = self.summary().data['alertas']; second = self.summary(pagina_alertas=2).data['alertas']
        self.assertEqual(first['count'], 14); self.assertEqual(len(first['results']), 10); self.assertEqual(len(second['results']), 4)
        self.assertFalse(set(row['id'] for row in first['results']) & set(row['id'] for row in second['results']))

    def test_period_and_pagination_validate_bounds(self):
        for params in [{'mes':0},{'mes':13},{'ano':1899},{'ano':10000},{'pagina_alertas':0},{'pagina_alertas':'bad'}]:
            self.assertEqual(self.summary(**params).status_code, 400)
        self.assertEqual(self.summary(ano=9999, mes=12).status_code, 200)

    def test_competence_changes_only_own_preference_without_business_privileges(self):
        self.permissions()
        other = Usuario.objects.create_user(username='pref_other', email='pref-other@example.test', password='test')
        old = (other.ultimo_mes, other.ultimo_ano)
        response = self.client.patch('/dashboard/api/competencia/', {'mes':2,'ano':2027,'is_superuser':True,'id':other.pk,'password':'new'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db();other.refresh_from_db()
        self.assertEqual((self.user.ultimo_mes,self.user.ultimo_ano),(2,2027));self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.check_password('Dashboard-test-918!'))
        self.assertEqual((other.ultimo_mes,other.ultimo_ano),old)
        self.assertEqual(self.client.get('/dashboard/api/competencia/').data, {'mes':2,'ano':2027})
        self.assertEqual(self.client.patch('/dashboard/api/competencia/', {'mes':13,'ano':2027}, format='json').status_code,400)

    def test_invalid_legacy_preference_falls_back_without_writing(self):
        self.user.ultimo_mes=0;self.user.ultimo_ano=0;self.user.save(update_fields=['ultimo_mes','ultimo_ano'])
        self.assertEqual(self.client.get('/dashboard/api/competencia/').data, {'mes':11,'ano':2026})
        self.user.refresh_from_db();self.assertEqual(self.user.ultimo_mes,0)

    @override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
    def test_session_writes_require_csrf_and_old_routes_only_redirect(self):
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.get('/dashboard/api/resumo/', {'empresa':self.company.pk}).status_code,200)
        self.assertEqual(client.patch('/dashboard/api/competencia/', {'mes':2,'ano':2027},format='json').status_code,403)
        token=client.get('/clientes/api/auth/csrf/').data['csrfToken']
        self.assertEqual(client.patch('/dashboard/api/competencia/', {'mes':2,'ano':2027},format='json',HTTP_X_CSRFTOKEN=token).status_code,200)
        for path in ['/dashboard/','/dashboard/dashboard/','/dashboard/competencia/']:
            response=client.get(path);self.assertEqual(response.status_code,302);self.assertEqual(response.url,'/clientes/app/dashboard')
        self.assertEqual(client.post('/dashboard/competencia/', {'mes':1,'ano':2020},HTTP_X_CSRFTOKEN=token).status_code,405)
