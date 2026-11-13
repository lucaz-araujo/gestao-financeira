"""Navegador real contra Django e PostgreSQL isolado; não usa dados locais."""
import os
from pathlib import Path
import secrets
import subprocess
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from clientes.models import Cliente, Uf, Municipio
from empresa.models import Empresa
from usuario.models import Usuario


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class BrowserTests(StaticLiveServerTestCase):
    def test_full_frontend(self):
        cache.clear()
        company = Empresa.objects.create(cnpj='1', razao='Empresa Alfa')
        other = Empresa.objects.create(cnpj='2', razao='Empresa Beta')
        uf = Uf.objects.create(sigla='CE', descricao='Ceará')
        Municipio.objects.create(uf=uf, codigo_ibge='2304400', descricao='Fortaleza')
        Cliente.objects.create(empresa=company, instituicao='Município de Fortaleza', uf=uf,
                               cnpj='11.222.333/0001-81', endereco='Rua A', numero='1', bairro='Centro', cep='60000-000')
        Cliente.objects.create(empresa=other, instituicao='Cliente de outra empresa', uf=uf)
        password = secrets.token_urlsafe(24)
        user = Usuario.objects.create_user(username='browser_e2e', password=password, email='browser@example.com')
        user.empresas.add(company, other)
        user.user_permissions.set(Permission.objects.filter(content_type__app_label='clientes'))
        user.user_permissions.add(Permission.objects.get(codename='add_recreceita'))
        screenshot_dir = '/tmp/gestao-clientes-e2e'
        Path(screenshot_dir).mkdir(exist_ok=True)
        env = {**os.environ, 'E2E_BASE_URL': self.live_server_url, 'E2E_USERNAME': user.username,
               'E2E_PASSWORD': password, 'E2E_SCREENSHOT_DIR': screenshot_dir,
               'PLAYWRIGHT_BROWSERS_PATH': os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/tmp/gestao-playwright')}
        result = subprocess.run(['node_modules/.bin/playwright', 'test', 'clientes.spec.ts'], cwd=settings.BASE_DIR, env=env, timeout=180)
        self.assertEqual(result.returncode, 0)
