from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from clientes.models import Cliente, Parceiro, Uf, Municipio, Liberacao, LiberacaoDatas
from empresa.models import Empresa
from usuario.models import Usuario


class ClientesAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Empresa.objects.create(cnpj='1', razao='Empresa A')
        cls.other_company = Empresa.objects.create(cnpj='2', razao='Empresa B')
        cls.uf = Uf.objects.create(sigla='CE', descricao='Ceará')
        cls.other_uf = Uf.objects.create(sigla='PI', descricao='Piauí')
        cls.city = Municipio.objects.create(uf=cls.uf, descricao='Fortaleza', codigo_ibge='2304400')
        cls.user = Usuario.objects.create_user(username='operador', email='op@example.com', password='test')
        cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='clientes'))
        cls.user.user_permissions.add(Permission.objects.get(codename='add_recreceita'))
        cls.customer = Cliente.objects.create(empresa=cls.company, instituicao='Cliente A',
                                             uf=cls.uf, cidade=cls.city, codigolayout='0001', codigoentidade='01')
        cls.other = Cliente.objects.create(empresa=cls.other_company, instituicao='Cliente B', uf=cls.uf)
        cls.partner = Parceiro.objects.create(empresa=cls.other_company, instituicao='Parceiro B', uf=cls.uf)

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}',
                                HTTP_X_EMPRESA_ID=str(self.company.pk))
        self.url = '/clientes/api/clientes/'
        self.customer_data = {'cnpj': '11.222.333/0001-81', 'endereco': 'Rua A',
                              'numero': '1', 'bairro': 'Centro', 'cep': '60000-000', 'uf': self.uf.pk}

    def test_requires_authentication_and_rejects_invalid_or_expired_jwt(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['code'], 'token_not_valid')
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_list_and_details_are_scoped_to_company(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([x['id'] for x in response.data['results']], [self.customer.pk])
        for method in ('get', 'patch', 'delete'):
            response = getattr(self.client, method)(f'{self.url}{self.other.pk}/')
            self.assertEqual(response.status_code, 404)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}',
                                HTTP_X_EMPRESA_ID=str(self.other_company.pk))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_missing_and_invalid_company_return_400(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, HTTP_X_EMPRESA_ID='abc').status_code, 400)

    def test_permissions_apply_to_reads_and_legacy_post_delete(self):
        self.user.user_permissions.clear()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(reverse('excluir_cliente', args=[self.customer.pk])).status_code, 403)

    def test_create_assigns_company_and_hides_credentials(self):
        response = self.client.post(self.url, {**self.customer_data, 'instituicao': 'Novo cliente',
                                    'empresa': self.other_company.pk, 'senhatcm': 'secret'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['empresa'], self.company.pk)
        self.assertNotIn('senhatcm', response.data)
        self.assertNotIn('token', response.data)
        created = Cliente.objects.get(pk=response.data['id'])
        self.assertEqual(created.senhatcm, 'secret')
        response = self.client.patch(f'{self.url}{created.pk}/', {'instituicao': 'Renomeado'}, format='json')
        self.assertEqual(response.status_code, 200)
        created.refresh_from_db()
        self.assertEqual(created.senhatcm, 'secret')

    def test_foreign_partner_and_inconsistent_city_are_rejected(self):
        response = self.client.post(self.url, {**self.customer_data, 'instituicao': 'Novo', 'parceiro': self.partner.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post(self.url, {**self.customer_data, 'instituicao': 'Novo', 'cidade': self.city.pk,
                                             'uf': self.other_uf.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('cidade', response.data)

    def test_document_and_entity_validation(self):
        for field, value in [('cnpj', '00000000000000'), ('resp_cpf', '00000000000'),
                             ('codigoentidade', '123'), ('codigoentidade', 'AB')]:
            response = self.client.patch(f'{self.url}{self.customer.pk}/', {field: value}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn(field, response.data)
        response = self.client.post(self.url, {**self.customer_data, 'instituicao': 'Duplicado', 'codigolayout': '0001',
                                             'codigoentidade': '01'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_uf_scope_applies_to_details_and_writes(self):
        self.user.uf = self.uf
        self.user.save()
        hidden = Cliente.objects.create(empresa=self.company, instituicao='Outro estado', uf=self.other_uf)
        self.assertEqual(self.client.get(f'{self.url}{hidden.pk}/').status_code, 404)
        response = self.client.patch(f'{self.url}{self.customer.pk}/',
                                     {'uf': self.other_uf.pk, 'cidade': None}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_release_creation_is_validated_and_preserves_protocol(self):
        url = '/clientes/api/liberacoes/'
        payload = {'cliente': self.customer.pk, 'competencia': '1', 'exercicio': 2026, 'usuario': 999}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['competencia'], '01')
        self.assertEqual(response.data['usuario'], self.user.pk)
        import hashlib
        from django.conf import settings
        expected = hashlib.md5(f'000101012026sucesso{settings.API_SECRET_KEY}'.encode('ascii')).hexdigest()
        self.assertEqual(response.data['chave'], expected)
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 400)
        payload['cliente'] = self.other.pk
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 400)
        payload.update(cliente=self.customer.pk, competencia='13')
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 400)

    def test_block_period_is_validated_on_create_and_patch(self):
        url = '/clientes/api/bloqueios/'
        payload = {'cliente': self.customer.pk, 'dt_ate': '2026-10-01', 'dt_aparte': '2026-10-31'}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['usuario'], self.user.pk)
        response = self.client.patch(f"{url}{response.data['id']}/", {'dt_ate': '2026-11-01'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('dt_aparte', response.data)
        self.assertEqual(self.client.post(url, {'cliente': self.customer.pk}, format='json').status_code, 400)

    def test_protected_delete_does_not_remove_dependents(self):
        block = LiberacaoDatas.objects.create(cliente=self.customer, dt_ate='2026-01-01', dt_aparte='2026-01-31')
        response = self.client.delete(f'{self.url}{self.customer.pk}/')
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Cliente.objects.filter(pk=self.customer.pk).exists())
        self.assertTrue(LiberacaoDatas.objects.filter(pk=block.pk).exists())

    def test_reports_and_shared_lookups(self):
        for kind in ('CL', 'CP', 'CC'):
            response = self.client.get(f'{self.url}relatorio/', {'tipo_relatorio': kind})
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['count'], 1)
        self.assertEqual(self.client.get(f'{self.url}aniversariantes/').status_code, 400)
        response = self.client.get(reverse('cidade', args=[self.uf.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['options'], [{'value': self.city.pk, 'text': self.city.descricao}])

    def test_session_lookups_and_csrf_enforcement(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.get(reverse('cidade', args=[self.uf.pk])).status_code, 200)
        self.assertEqual(client.post(self.url, {'instituicao': 'Novo'}, format='json').status_code, 403)

    @patch('clientes.views.busca_cep', return_value=[{'cep': '60000-000'}])
    def test_cep_returns_data_instead_of_html(self, lookup):
        response = self.client.get(reverse('retorna_cep'), {'logradouro': 'Rua Teste'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'results': [{'cep': '60000-000'}]})

    def test_release_does_not_expose_generic_update(self):
        response = self.client.post('/clientes/api/liberacoes/',
                                    {'cliente': self.customer.pk, 'competencia': '2', 'exercicio': 2026}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/clientes/api/liberacoes/{response.data['id']}/"
        self.assertEqual(self.client.put(url, {}, format='json').status_code, 405)
        self.assertEqual(self.client.patch(url, {}, format='json').status_code, 405)

    def test_required_fields_and_partner_crud(self):
        response = self.client.post(self.url, {'instituicao': 'Incompleto'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('cnpj', response.data)
        url = '/clientes/api/parceiros/'
        payload = {**self.customer_data, 'instituicao': 'Parceiro novo', 'cidade': self.city.pk}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        self.assertEqual(response.data['empresa'], self.company.pk)
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 400)
        response = self.client.patch(f'{url}{pk}/', {'libera_clientes': False}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['libera_clientes'])
        self.assertEqual(self.client.delete(f'{url}{pk}/').status_code, 204)

    def test_relations_and_reports_never_expose_other_company(self):
        block = LiberacaoDatas.objects.create(cliente=self.other, dt_ate='2026-01-01', dt_aparte='2026-01-31')
        self.assertEqual(self.client.get(f'/clientes/api/bloqueios/{block.pk}/').status_code, 404)
        response = self.client.get('/clientes/api/bloqueios/')
        self.assertEqual(response.data['count'], 0)
        response = self.client.get('/clientes/api/parceiros/relatorio/')
        self.assertEqual(response.data['count'], 0)
        response = self.client.post('/clientes/api/bloqueios/',
                                    {'cliente': self.other.pk, 'dt_ate': '2026-01-01', 'dt_aparte': '2026-01-31'}, format='json')
        self.assertEqual(response.status_code, 400)
