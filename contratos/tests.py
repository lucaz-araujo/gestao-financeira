from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from clientes.models import Cliente, Uf
from empresa.models import Empresa
from notas.models import Nota
from produtos.models import Produto
from usuario.models import Usuario
from .models import Contrato, ContratoProduto, ContratoRenovacao


class ContratoAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(cnpj='1', razao='Empresa A')
        cls.outra = Empresa.objects.create(cnpj='2', razao='Empresa B')
        cls.uf = Uf.objects.create(sigla='CE', descricao='Ceará')
        cls.user = Usuario.objects.create_user(username='contrato_test', email='con@example.com', password='test')
        cls.user.empresas.add(cls.empresa)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='contratos'))
        cls.cliente = Cliente.objects.create(empresa=cls.empresa, instituicao='Cliente A', uf=cls.uf)
        cls.outro_cliente = Cliente.objects.create(empresa=cls.outra, instituicao='Cliente B')
        cls.produto = Produto.objects.create(empresa=cls.empresa, descricao='Produto A', sigla='PROD', valor=100)
        cls.outro_produto = Produto.objects.create(empresa=cls.outra, descricao='Produto B', sigla='OUTRO', valor=200)
        cls.contrato = Contrato.objects.create(empresa=cls.empresa, cliente=cls.cliente, numero='001', dia_nota=10,
            dt_data_contrato='2026-01-01', dt_data_final='2026-12-31', exercicio=2026, objeto='Serviços',
            valor_bruto=100, perc_iss=5, perc_irpj=2, valor_iss=5, valor_irpj=2, valor_liquido=93)
        cls.item = ContratoProduto.objects.create(contrato=cls.contrato, produtos=cls.produto, valor='12.12345')
        cls.renovacao = ContratoRenovacao.objects.create(contrato=cls.contrato, dt_data_inicio='2027-01-01', dt_data_final='2027-12-31')
        cls.oculto = Contrato.objects.create(empresa=cls.outra, cliente=cls.outro_cliente, numero='OUTRO', valor_liquido=999)

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(self.user)), HTTP_X_EMPRESA_ID=str(self.empresa.pk))
        self.url = '/contratos/api/contratos/'
        self.path = f'{self.url}{self.contrato.pk}/'

    def payload(self, **overrides):
        data = {'cliente': self.cliente.pk, 'numero': 'NOVO', 'dia_nota': 15, 'exercicio': 2026,
                'dt_data_contrato': '2026-01-01', 'dt_data_final': '2026-12-31', 'objeto': 'Objeto',
                'valor_bruto': '100.00', 'perc_iss': '5.00', 'perc_irpj': '2.00',
                'valor_iss': '5.00', 'valor_irpj': '2.00', 'valor_liquido': '93.00',
                'itens': [{'produtos': self.produto.pk, 'valor': '12.12345'}],
                'renovacoes': [{'dt_data_inicio': '2027-01-01', 'dt_data_final': '2027-12-31'}]}
        return {**data, **overrides}

    def note(self):
        return Nota.objects.create(empresa=self.empresa, contrato=self.contrato, numero='NF-1',
                                   competencia=1, exercicio=2026, dt_data_emissao=timezone.now(), valor_liquido=93)

    def test_requires_authentication_company_and_permissions(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid')
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(self.user)))
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, {'empresa': self.outra.pk}).status_code, 403)

    def test_company_scope_and_foreign_relations(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([r['id'] for r in response.data['results']], [self.contrato.pk])
        for method in ('get', 'patch', 'delete'):
            self.assertEqual(getattr(self.client, method)(f'{self.url}{self.oculto.pk}/', {}, format='json').status_code, 404)
        for changes in ({'cliente': self.outro_cliente.pk}, {'itens': [{'produtos': self.outro_produto.pk, 'valor': '1'}]}):
            response = self.client.post(self.url, self.payload(**changes), format='json')
            self.assertEqual(response.status_code, 400, response.data)

    def test_create_nested_records_and_ignore_company_injection(self):
        response = self.client.post(self.url, self.payload(empresa=self.outra.pk), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        obj = Contrato.objects.get(pk=response.data['id'])
        self.assertEqual(obj.empresa_id, self.empresa.pk)
        self.assertEqual(obj.produtosCont.get().valor, Decimal('12.12345'))
        self.assertEqual(obj.renovacao.count(), 1)
        self.assertFalse(response.data['tem_nota'])

    def test_update_children_preserves_ids_and_omitted_lists(self):
        response = self.client.patch(self.path, {'numero': 'ATUALIZADO'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['itens'][0]['id'], self.item.pk)
        self.assertEqual(response.data['renovacoes'][0]['id'], self.renovacao.pk)
        response = self.client.patch(self.path, {'itens': [{'id': self.item.pk, 'produtos': self.produto.pk, 'valor': '19.54321'}], 'renovacoes': []}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.item.refresh_from_db()
        self.assertEqual(self.item.valor, Decimal('19.54321'))
        self.assertEqual(response.data['itens'][0]['valor'], '19.54321')
        self.assertFalse(ContratoRenovacao.objects.filter(pk=self.renovacao.pk).exists())

    def test_invalid_nested_data_does_not_save_parent_or_other_children(self):
        before = Contrato.objects.count()
        invalid = self.payload(renovacoes=[{'dt_data_inicio': '2028-01-01', 'dt_data_final': '2027-01-01'}])
        self.assertEqual(self.client.post(self.url, invalid, format='json').status_code, 400)
        self.assertEqual(Contrato.objects.count(), before)
        response = self.client.patch(self.path, {'numero': 'NAO SALVAR', 'itens': [{'produtos': self.produto.pk, 'valor': '-1'}]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.contrato.refresh_from_db()
        self.assertEqual(self.contrato.numero, '001')
        self.assertEqual(self.contrato.produtosCont.count(), 1)
        for data in ({'itens': [{'id': self.item.pk}]}, {'renovacoes': [{'id': self.renovacao.pk}]}):
            self.assertEqual(self.client.patch(self.path, data, format='json').status_code, 400)

    def test_unexpected_child_failure_rolls_back_entire_create(self):
        before = (Contrato.objects.count(), ContratoProduto.objects.count())
        with patch('contratos.serializers.ContratoRenovacao.objects.create', side_effect=RuntimeError('simulated failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, self.payload(), format='json')
        self.assertEqual((Contrato.objects.count(), ContratoProduto.objects.count()), before)

    def test_foreign_and_duplicate_nested_ids_are_rejected(self):
        foreign = ContratoProduto.objects.create(contrato=self.oculto, produtos=self.outro_produto, valor=1)
        for ids in ([foreign.pk], [self.item.pk, self.item.pk]):
            response = self.client.patch(self.path, {'itens': [{'id': pk, 'produtos': self.produto.pk, 'valor': '1'} for pk in ids]}, format='json')
            self.assertEqual(response.status_code, 400)
        response = self.client.post(self.url, self.payload(itens=[{'id': self.item.pk, 'produtos': self.produto.pk, 'valor': '1'}]), format='json')
        self.assertEqual(response.status_code, 400)

    def test_dates_day_year_percentages_and_currency_validation(self):
        invalid = [('dia_nota', 0), ('dia_nota', 32), ('exercicio', 0), ('valor_bruto', '-1'),
                   ('perc_iss', '100.01'), ('valor_liquido', '0.001'), ('dt_data_final', '2025-12-31')]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                response = self.client.post(self.url, self.payload(**{field: value}), format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data)

    def test_financial_values_are_not_silently_recalculated(self):
        self.client.patch(self.path, {'valor_liquido': '85.00'}, format='json')
        response = self.client.patch(self.path, {'numero': 'VALORES'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['valor_liquido'], '85.00')
        self.assertEqual(response.data['valor_bruto'], '100.00')
        self.assertEqual(response.data['valor_iss'], '5.00')

    def test_calculation_rounds_decimal_and_does_not_write(self):
        response = self.client.post(self.url + 'calcular/', {'valor_bruto': '10.10', 'perc_iss': '5', 'perc_irpj': '0'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {'valor_iss': '0.51', 'valor_irpj': '0.00', 'valor_liquido': '9.59'})
        self.assertEqual(self.client.post(self.url + 'calcular/', {'valor_bruto': '1', 'perc_iss': '90', 'perc_irpj': '20'}, format='json').status_code, 400)
        self.contrato.refresh_from_db()
        self.assertEqual(self.contrato.valor_bruto, Decimal('100'))

    def test_delete_without_notes_removes_only_owned_children(self):
        self.assertEqual(self.client.delete(self.path).status_code, 204)
        self.assertFalse(Contrato.objects.filter(pk=self.contrato.pk).exists())
        self.assertFalse(ContratoProduto.objects.filter(pk=self.item.pk).exists())
        self.assertFalse(ContratoRenovacao.objects.filter(pk=self.renovacao.pk).exists())
        self.assertTrue(Produto.objects.filter(pk=self.produto.pk).exists())
        self.assertTrue(Cliente.objects.filter(pk=self.cliente.pk).exists())

    def test_notes_block_deletion_and_customer_change(self):
        note = self.note()
        self.assertEqual(self.client.delete(self.path).status_code, 409)
        self.assertTrue(ContratoProduto.objects.filter(pk=self.item.pk).exists())
        self.assertTrue(ContratoRenovacao.objects.filter(pk=self.renovacao.pk).exists())
        self.assertTrue(Nota.objects.filter(pk=note.pk).exists())
        other = Cliente.objects.create(empresa=self.empresa, instituicao='Outro')
        response = self.client.patch(self.path, {'cliente': other.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        detail = self.client.get(self.path)
        self.assertTrue(detail.data['tem_nota'])
        self.assertEqual(detail.data['notas'][0]['numero'], 'NF-1')

    def test_filters_report_total_and_print_alias(self):
        response = self.client.get(self.url, {'search': 'Cliente A', 'page_size': 1})
        self.assertEqual(response.data['count'], 1)
        response = self.client.get(self.url + 'relatorio/', {'tipo_relatorio': 'C', 'dt_inicial': '2026-01-01', 'dt_final': '2026-12-31'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['valor_total'], '93.00')
        self.assertEqual(response.data['results'][0]['itens'][0]['produto_nome'], 'Produto A')
        for params in ({'ativo': 'invalid'}, {'cliente': 'x'}, {'dt_inicial': '2026-01-01'}):
            self.assertEqual(self.client.get(self.url, params).status_code, 400)
        self.assertEqual(self.client.get(reverse('print_contrato', args=[self.contrato.pk])).url, f'/clientes/app/contratos?imprimir={self.contrato.pk}')

    def test_uf_scope_on_queries_and_customer_selection(self):
        self.user.uf = self.uf
        self.user.save()
        other_uf = Uf.objects.create(sigla='PI', descricao='Piauí')
        other = Cliente.objects.create(empresa=self.empresa, instituicao='Outro estado', uf=other_uf)
        contract = Contrato.objects.create(empresa=self.empresa, cliente=other)
        self.assertEqual(self.client.get(f'{self.url}{contract.pk}/').status_code, 404)
        self.assertEqual(self.client.post(self.url, self.payload(cliente=other.pk), format='json').status_code, 400)
        self.assertEqual(self.client.get(self.url + 'opcoes/', {'tipo': 'clientes'}).data['count'], 1)

    def test_read_only_permissions_and_session_csrf(self):
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='contratos', codename='view_contrato'))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        for path, data in ((self.url, self.payload()), (reverse('edit_contrato', args=[self.contrato.pk]), self.payload()), (reverse('delete_contrato', args=[self.contrato.pk]), {})):
            self.assertEqual(self.client.post(path, data, format='json').status_code, 403)
        session_client = APIClient(enforce_csrf_checks=True)
        session_client.force_login(self.user)
        self.assertEqual(session_client.post(self.url, {}, format='json').status_code, 403)

    def test_contract_only_user_can_load_scoped_options(self):
        for kind, field in (('clientes', 'instituicao'), ('produtos', 'descricao')):
            response = self.client.get(self.url + 'opcoes/', {'tipo': kind})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['count'], 1)
            self.assertIn(field, response.data['results'][0])
        self.assertEqual(self.client.get(self.url + 'opcoes/', {'tipo': 'invalid'}).status_code, 400)
