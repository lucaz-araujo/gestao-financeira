import importlib.util
import json
import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch, Mock
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.exceptions import ImproperlyConfigured
from django.core.cache import cache
from django.http import HttpResponse
from django.test import SimpleTestCase, TestCase, TransactionTestCase, RequestFactory, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from clientes.models import Cliente, Liberacao
from empresa.models import Empresa
from core.middleware import TrustedProxyMiddleware
from core.operations import legacy_audit


class ProductionSettingsTests(SimpleTestCase):
    def load_profile(self, **values):
        import layCliente.settings as base
        env = {'ALLOWED_HOSTS': 'financeiro.example.test', 'DATABASE_USE_ADMIN': 'False', 'TRUST_PROXY_HTTPS': 'True', 'CACHE_URL': '', **values}
        spec = importlib.util.spec_from_file_location('layCliente._production_test', Path(base.BASE_DIR) / 'layCliente' / 'production.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, env), patch.multiple(base, PUBLIC_APP_URL='https://financeiro.example.test', SECRET_KEY='production-fixture-1234567890-ABCDEFGHIJKLMNOPQRSTUVWXYZ-only-tests'):
            spec.loader.exec_module(module)
        return module

    def test_profile_enforces_https_and_secure_cookies_independent_of_local_debug(self):
        profile = self.load_profile()
        self.assertFalse(profile.DEBUG)
        self.assertTrue(profile.SECURE_SSL_REDIRECT)
        self.assertTrue(profile.SESSION_COOKIE_SECURE and profile.CSRF_COOKIE_SECURE and profile.CLIENTES_AUTH_COOKIE_SECURE)
        self.assertEqual(profile.SECURE_PROXY_SSL_HEADER, ('HTTP_X_FORWARDED_PROTO', 'https'))
        self.assertGreater(profile.SECURE_HSTS_SECONDS, 0)
        self.assertNotIn('locmem', profile.CACHES['default']['BACKEND'])

    def test_profile_refuses_wildcards_missing_domain_or_database_admin(self):
        for values in [{'ALLOWED_HOSTS': '*'}, {'ALLOWED_HOSTS': ''}, {'ALLOWED_HOSTS': 'other.example.test'}, {'DATABASE_USE_ADMIN': 'True'}]:
            with self.subTest(values=values), self.assertRaises(ImproperlyConfigured):
                self.load_profile(**values)

    @override_settings(TRUST_PROXY_HTTPS=True, TRUSTED_PROXY_IPS=['127.0.0.1'])
    def test_proxy_does_not_accept_forwarded_identity_from_public_peer(self):
        request = RequestFactory().get('/', REMOTE_ADDR='198.51.100.7', HTTP_X_REAL_IP='192.0.2.2', HTTP_X_FORWARDED_PROTO='https')
        TrustedProxyMiddleware(lambda req: HttpResponse())(request)
        self.assertEqual(request.META['REMOTE_ADDR'], '198.51.100.7')
        self.assertNotIn('HTTP_X_FORWARDED_PROTO', request.META)

    @override_settings(TRUST_PROXY_HTTPS=True, TRUSTED_PROXY_IPS=['127.0.0.1'])
    def test_proxy_uses_only_ip_set_by_trusted_proxy(self):
        request = RequestFactory().get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_REAL_IP='198.51.100.7')
        TrustedProxyMiddleware(lambda req: HttpResponse())(request)
        self.assertEqual(request.META['REMOTE_ADDR'], '198.51.100.7')

    @override_settings(SECRET_KEY='rotation-fixture-secret-only-tests', SECRET_KEY_FALLBACKS=[])
    def test_rotation_candidates_are_private_and_never_activated_or_printed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rotation.json'; output = StringIO()
            call_command('preparar_rotacao', output=str(path), stdout=output)
            data = json.loads(path.read_text())
            self.assertFalse(data['ativado'])
            self.assertGreaterEqual(len(data['secret_key_nova']), 64)
            self.assertNotIn(data['secret_key_nova'], output.getvalue())
            self.assertEqual(data['secret_key_fallbacks_durante_transicao'], [settings.SECRET_KEY])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(CommandError):
                call_command('preparar_rotacao', output=str(path))


class TokenThrottleTests(TestCase):
    def setUp(self):
        cache.clear(); self.client = APIClient()

    def test_raw_jwt_login_is_limited_and_forwarded_header_cannot_bypass(self):
        for attempt in range(10):
            response = self.client.post('/api/token/', {'username': 'missing-test', 'password': 'not-a-real-password'}, format='json', HTTP_X_FORWARDED_FOR=f'192.0.2.{attempt + 1}')
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response['Cache-Control'], 'no-store')
        response = self.client.post('/api/token/', {}, format='json', HTTP_X_FORWARDED_FOR='198.51.100.9')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        # O alias e o login React compartilham o limite por IP real.
        self.assertEqual(self.client.post('/clientes/api/auth/login/', {}, format='json').status_code, 429)

    def test_refresh_uses_independent_limit(self):
        for _ in range(60):
            self.assertEqual(self.client.post('/api/token/refresh/', {'refresh': 'invalid'}, format='json').status_code, 401)
        self.assertEqual(self.client.post('/api/token/refresh/', {}, format='json').status_code, 429)
        self.assertEqual(self.client.post('/api/token/', {}, format='json').status_code, 400)


class OperationalAuditTests(TransactionTestCase):
    def setUp(self):
        company = Empresa.objects.create(cnpj='1', razao='Empresa de diagnóstico')
        self.customer = Cliente.objects.create(empresa=company, instituicao='Cliente de diagnóstico', codigolayout='0001', codigoentidade='01')
        Cliente.objects.create(empresa=company, instituicao='Outro cliente de diagnóstico', codigolayout='0001', codigoentidade='01')
        for index in range(2):
            Liberacao.objects.create(cliente=self.customer, competencia='01', exercicio=2026, codigo='01' if index == 0 else '02', codigo_layout='0001', chave=f'fixture-key-{index}', dt_liberacao=timezone.now())

    def test_audit_distinguishes_ambiguous_clients_from_historical_differences_without_writes(self):
        before = list(Liberacao.objects.values('pk', 'chave', 'codigo'))
        report = legacy_audit()
        self.assertEqual(len(report['identidades_ambiguas']), 1)
        self.assertEqual(len(report['periodos_com_multiplas_liberacoes']), 1)
        self.assertEqual(len(report['liberacoes_com_codigos_diferentes_do_cadastro_atual_ids']), 1)
        self.assertEqual(before, list(Liberacao.objects.values('pk', 'chave', 'codigo')))

    def test_report_is_private_and_stdout_contains_only_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'; output = StringIO()
            with patch('core.management.commands.verificar_operacao.fiscal_audit', return_value=[]):
                call_command('verificar_operacao', report=str(path), stdout=output)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('codigolayout', output.getvalue())
            self.assertNotIn('Cliente de diagnóstico', output.getvalue())
            self.assertEqual(json.loads(output.getvalue())['grupos_clientes_ambiguos'], 1)
            self.assertEqual(Cliente.objects.count(), 2)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.example.test')
    def test_smtp_check_never_sends_email_or_exposes_connection_error(self):
        transport = Mock(); transport.open.side_effect = RuntimeError('synthetic-private-credential')
        output = StringIO()
        with patch('core.management.commands.verificar_operacao.get_connection', return_value=transport), patch('core.management.commands.verificar_operacao.fiscal_audit', return_value=[]):
            call_command('verificar_operacao', smtp=True, stdout=output)
        self.assertFalse(json.loads(output.getvalue())['smtp_conexao'])
        transport.send_messages.assert_not_called()
        transport.close.assert_called_once()
        self.assertNotIn('synthetic-private-credential', output.getvalue())
