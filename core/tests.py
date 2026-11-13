import tempfile
from django.core.exceptions import BadRequest, PermissionDenied
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.template.loader import get_template
from django.urls import include, path
from django.views.defaults import server_error


def invalid_request(request):
    raise BadRequest('synthetic-private-request')


def forbidden(request):
    raise PermissionDenied('synthetic-private-permission')


def failed(request):
    raise RuntimeError('synthetic-private-server-details')


# Rotas de falha existem somente neste URLConf de testes.
urlpatterns = [
    path('_errors/400/', invalid_request),
    path('_errors/403/', forbidden),
    path('_errors/500/', failed),
    path('', include('layCliente.urls')),
]


@override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'], ROOT_URLCONF=__name__)
class SharedPagesTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def assert_error(self, path, code, heading):
        response = self.client.get(path)
        self.assertContains(response, heading, status_code=code)
        self.assertContains(response, '<p class="status">' + str(code) + '</p>', status_code=code)
        self.assertContains(response, 'alt="Layout Sistemas"', status_code=code)
        self.assertContains(response, 'href="/clientes/app/"', status_code=code)
        self.assertNotContains(response, 'synthetic-private', status_code=code)
        self.assertNotContains(response, '<script', status_code=code)
        self.assertNotContains(response, 'AdminLTE', status_code=code)
        return response

    def test_bad_request_uses_localized_400(self):
        self.assert_error('/_errors/400/', 400, 'Solicitação inválida')

    def test_forbidden_is_403_not_the_old_404_content(self):
        self.assert_error('/_errors/403/', 403, 'Acesso negado')

    def test_missing_page_does_not_echo_private_path_or_query(self):
        response = self.assert_error('/synthetic-private-path/?token=synthetic-private-token', 404, 'Página não encontrada')
        self.assertNotContains(response, 'token=', status_code=404)

    def test_server_error_renders_without_database_or_frontend_manifest(self):
        with tempfile.TemporaryDirectory() as directory, self.settings(BASE_DIR=directory):
            self.assert_error('/_errors/500/', 500, 'Não foi possível concluir a solicitação')

    def test_server_error_does_not_access_user_or_session(self):
        class Unavailable:
            def __getattr__(self, name):
                raise AssertionError('Dependência indisponível')
        request = RequestFactory().get('/_errors/500/')
        request.user = Unavailable()
        request.session = Unavailable()
        response = server_error(request)
        self.assertEqual(response.status_code, 500)
        self.assertIn('Layout Sistemas', response.content.decode())

    def test_error_and_public_invoice_templates_compile_independently(self):
        for template in ['400.html', '403.html', '404.html', '500.html', 'nota_publica.html', 'notas_cliente_publicas.html', 'nota_email.html']:
            with self.subTest(template=template):
                self.assertIsNotNone(get_template(template))

    def test_spa_routes_share_the_system_title(self):
        for route in ['dashboard', 'perfil', 'clientes', 'recadastramento']:
            with self.subTest(route=route):
                response = self.client.get('/clientes/app/' + route)
                self.assertContains(response, '<title>Gestão Financeira · Layout Sistemas</title>')
                self.assertContains(response, '<div id="root"></div>')

    def test_django_admin_login_keeps_its_own_templates(self):
        response = self.client.get('/admin/login/')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'name="username"')

    def test_auth_api_errors_still_use_json(self):
        response = self.client.get('/clientes/api/auth/me/')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIsInstance(response.json(), dict)
