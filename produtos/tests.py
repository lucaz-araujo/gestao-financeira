from decimal import Decimal
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from clientes.models import Cliente, Liberacao, Uf
from contratos.models import Contrato, ContratoProduto
from empresa.models import Empresa
from usuario.models import Usuario
from .models import Produto


class ProdutoAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(cnpj='1', razao='Empresa A')
        cls.outra = Empresa.objects.create(cnpj='2', razao='Empresa B')
        cls.user = Usuario.objects.create_user(username='produtos_test', email='prod@example.com', password='test')
        cls.user.empresas.add(cls.empresa)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='produtos'))
        cls.produto = Produto.objects.create(empresa=cls.empresa, descricao='Folha de pagamento', sigla='FOLHA', valor='150.10')
        cls.servico = Produto.objects.create(empresa=cls.empresa, descricao='Treinamento', sigla='TREIN', tipo_produto='S', valor='0')
        cls.oculto = Produto.objects.create(empresa=cls.outra, descricao='Outra empresa', sigla='OUTRO', valor='999')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(self.user)), HTTP_X_EMPRESA_ID=str(self.empresa.pk))
        self.url = '/produtos/api/produtos/'

    def test_authentication_and_company_are_required(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid')
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(self.user)))
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, {'empresa': 'abc'}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {'empresa': self.outra.pk}).status_code, 403)

    def test_list_search_type_filter_and_pagination(self):
        response = self.client.get(self.url, {'page_size': 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIsNotNone(response.data['next'])
        self.assertEqual(self.client.get(self.url, {'search': 'folha'}).data['results'][0]['id'], self.produto.pk)
        response = self.client.get(self.url, {'tipo_produto': 'S'})
        self.assertEqual([x['id'] for x in response.data['results']], [self.servico.pk])
        self.assertEqual(self.client.get(self.url, {'tipo_produto': 'X'}).status_code, 400)

    def test_cross_company_objects_are_hidden_for_all_operations(self):
        path = f'{self.url}{self.oculto.pk}/'
        for method in ('get', 'patch', 'delete'):
            response = getattr(self.client, method)(path, {'descricao': 'Tentativa'}, format='json')
            self.assertEqual(response.status_code, 404)
        self.oculto.refresh_from_db()
        self.assertEqual(self.oculto.descricao, 'Outra empresa')

    def test_crud_and_company_cannot_be_reassigned(self):
        response = self.client.post(self.url, {'descricao': 'Novo serviço', 'sigla': 'NOVO', 'tipo_produto': 'S',
                                             'valor': '1234.56', 'empresa': self.outra.pk}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['empresa'], self.empresa.pk)
        self.assertEqual(response.data['valor'], '1234.56')
        pk = response.data['id']
        response = self.client.patch(f'{self.url}{pk}/', {'valor': '0.00', 'empresa': self.outra.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Produto.objects.get(pk=pk).valor, Decimal('0'))
        self.assertEqual(response.data['empresa'], self.empresa.pk)
        self.assertEqual(self.client.delete(f'{self.url}{pk}/').status_code, 204)
        self.assertFalse(Produto.objects.filter(pk=pk).exists())

    def test_validation_of_price_lengths_choices_and_required_fields(self):
        payload = {'descricao': 'Produto', 'sigla': 'PROD', 'valor': '1.00', 'tipo_produto': 'P'}
        cases = [('descricao', ''), ('descricao', 'x' * 61), ('sigla', None), ('sigla', ' '),
                 ('sigla', 'LONGAA'), ('tipo_produto', 'X'), ('valor', None), ('valor', '-0.01'),
                 ('valor', '0.001'), ('valor', '100000000.00'), ('valor', 'NaN')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                response = self.client.post(self.url, {**payload, field: value}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data)
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        for field in ('descricao', 'sigla', 'valor'):
            self.assertIn(field, response.data)

    def test_model_validation_is_available_outside_api(self):
        with self.assertRaises(ValidationError):
            Produto(descricao='Produto', sigla='PROD', valor=Decimal('-1')).clean()

    def test_permissions_apply_to_reads_and_writes_and_legacy_post(self):
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='produtos', codename='view_produto'))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, {}).status_code, 403)
        self.assertEqual(self.client.patch(f'{self.url}{self.produto.pk}/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'{self.url}{self.produto.pk}/').status_code, 403)
        self.assertEqual(self.client.post(reverse('edit_produto', args=[self.produto.pk]), {}).status_code, 403)
        self.assertEqual(self.client.post(reverse('excluir_produto', args=[self.produto.pk])).status_code, 403)
        self.user.user_permissions.clear()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.head(self.url).status_code, 403)

    def test_protected_contracts_and_releases_are_not_deleted(self):
        cliente = Cliente.objects.create(empresa=self.empresa, instituicao='Cliente')
        contrato = Contrato.objects.create(empresa=self.empresa, cliente=cliente)
        link = ContratoProduto.objects.create(contrato=contrato, produtos=self.produto, valor=100)
        path = f'{self.url}{self.produto.pk}/'
        self.assertEqual(self.client.delete(path).status_code, 409)
        self.assertTrue(ContratoProduto.objects.filter(pk=link.pk).exists())
        link.delete()
        release = Liberacao.objects.create(cliente=cliente, produto=self.produto, competencia='01',
                                            exercicio=2026, dt_liberacao=timezone.now(), chave='produto-test')
        self.assertEqual(self.client.delete(path).status_code, 409)
        self.assertTrue(Liberacao.objects.filter(pk=release.pk).exists())
        self.assertTrue(Produto.objects.filter(pk=self.produto.pk).exists())

    def test_session_csrf_and_legacy_routes(self):
        session_client = APIClient(enforce_csrf_checks=True)
        session_client.force_login(self.user)
        session = session_client.session
        session['empresa'] = self.empresa.pk
        session.save()
        self.assertEqual(session_client.get(reverse('list_produtos')).status_code, 200)
        self.assertEqual(session_client.post(reverse('new_produto'), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse('edit_produto', args=[self.produto.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse('edit_produto', args=[self.produto.pk]),
                                          {'descricao': 'Atualizado', 'sigla': 'NOVO', 'valor': '10'}, format='json').status_code, 200)
        self.assertEqual(self.client.get(reverse('produtos_frontend')).url, '/clientes/app/produtos')

    def test_user_uf_does_not_filter_products_or_bypass_company(self):
        self.user.uf = Uf.objects.create(sigla='CE', descricao='Ceará')
        self.user.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
