from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from empresa.models import Empresa
from usuario.models import Usuario


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class FrontendAuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = Usuario.objects.create_user(username='frontend', password='test', email='front@example.com')
        self.company = Empresa.objects.create(cnpj='1', razao='Empresa permitida')
        self.other = Empresa.objects.create(cnpj='2', razao='Empresa não permitida')
        self.user.empresas.add(self.company)
        self.user.user_permissions.add(Permission.objects.get(codename='add_cliente'))
        self.root = '/clientes/api/auth/'
        self.csrf = self.client.get(self.root + 'csrf/').data['csrfToken']

    def login(self, **kwargs):
        response = self.client.post(self.root + 'login/', {'username': 'frontend', 'password': 'test'},
                                format='json', HTTP_X_CSRFTOKEN=self.csrf, **kwargs)
        if response.status_code == 200:
            self.csrf = response.data['csrfToken']
        return response

    def test_login_and_current_user_expose_only_authorized_companies(self):
        response = self.login()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn('refresh', response.data)
        cookie = response.cookies['clientes_refresh']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], self.root)
        self.assertEqual(response['Cache-Control'], 'no-store')
        response = self.client.get(self.root + 'me/', HTTP_AUTHORIZATION='Bearer ' + response.data['access'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual([x['id'] for x in response.data['empresas']], [self.company.pk])
        self.assertIn('clientes.add_cliente', response.data['permissions'])

    def test_cookie_endpoints_require_csrf(self):
        response = self.client.post(self.root + 'login/', {'username': 'frontend', 'password': 'test'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.login()
        for path in ('refresh/', 'logout/'):
            self.assertEqual(self.client.post(self.root + path).status_code, 403)
        self.assertEqual(self.client.post(self.root + 'logout/', HTTP_X_CSRFTOKEN=self.csrf,
                                         HTTP_ORIGIN='https://malicioso.example').status_code, 403)

    def test_rotation_rejects_reuse_and_logout_revokes_refresh(self):
        response = self.login()
        original = response.cookies['clientes_refresh'].value
        response = self.client.post(self.root + 'refresh/', HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(response.status_code, 200, response.data)
        rotated = response.cookies['clientes_refresh'].value
        self.assertNotEqual(original, rotated)
        self.client.cookies['clientes_refresh'] = original
        self.assertEqual(self.client.post(self.root + 'refresh/', HTTP_X_CSRFTOKEN=self.csrf).status_code, 401)
        self.client.cookies['clientes_refresh'] = rotated
        self.assertEqual(self.client.post(self.root + 'logout/', HTTP_X_CSRFTOKEN=self.csrf).status_code, 204)
        self.client.cookies['clientes_refresh'] = rotated
        self.assertEqual(self.client.post(self.root + 'refresh/', HTTP_X_CSRFTOKEN=self.csrf).status_code, 401)

    def test_invalid_login_and_missing_or_invalid_refresh_are_401(self):
        response = self.client.post(self.root + 'login/', {'username': 'frontend', 'password': 'wrong'},
                                    format='json', HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.post(self.root + 'refresh/', HTTP_X_CSRFTOKEN=self.csrf).status_code, 401)
        self.client.cookies['clientes_refresh'] = 'invalid'
        self.assertEqual(self.client.post(self.root + 'refresh/', HTTP_X_CSRFTOKEN=self.csrf).status_code, 401)

    def test_login_is_throttled(self):
        for _ in range(10):
            self.client.post(self.root + 'login/', {}, format='json', HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(self.login().status_code, 429)

    def test_options_are_scoped_for_creation_only_user(self):
        from clientes.models import Parceiro
        Parceiro.objects.create(empresa=self.company, instituicao='Permitido')
        Parceiro.objects.create(empresa=self.other, instituicao='Oculto')
        response = self.login()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'], HTTP_X_EMPRESA_ID=str(self.company.pk))
        response = self.client.get('/clientes/api/opcoes/?tipo=parceiros')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([x['instituicao'] for x in response.data['results']], ['Permitido'])
        self.assertEqual(self.client.get('/clientes/api/opcoes/?tipo=invalido').status_code, 400)
