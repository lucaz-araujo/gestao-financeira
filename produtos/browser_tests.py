import os
from pathlib import Path
import secrets
import subprocess

from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from clientes.models import Cliente
from contratos.models import Contrato, ContratoProduto
from empresa.models import Empresa
from usuario.models import Usuario
from .models import Produto


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class ProdutoBrowserTests(StaticLiveServerTestCase):
    def test_product_frontend(self):
        cache.clear()
        empresa = Empresa.objects.create(cnpj='1', razao='Empresa Alfa')
        outra = Empresa.objects.create(cnpj='2', razao='Empresa Beta')
        password = secrets.token_urlsafe(24)
        editor = Usuario.objects.create_user(username='prod_browser', email='prod-browser@example.com', password=password)
        editor.empresas.add(empresa, outra)
        editor.user_permissions.set(Permission.objects.filter(content_type__app_label='produtos'))
        reader = Usuario.objects.create_user(username='prod_reader', email='prod-reader@example.com', password=password)
        reader.empresas.add(empresa)
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='produtos', codename='view_produto'))
        fixed = Produto.objects.create(empresa=empresa, descricao='Licença vinculada', sigla='FIXO', valor='100.00')
        Produto.objects.create(empresa=empresa, descricao='Serviço inicial', sigla='SERV', tipo_produto='S', valor='0.00')
        Produto.objects.create(empresa=outra, descricao='Produto empresa Beta', sigla='BETA', valor='999.00')
        cliente = Cliente.objects.create(empresa=empresa, instituicao='Cliente do contrato')
        contrato = Contrato.objects.create(empresa=empresa, cliente=cliente)
        ContratoProduto.objects.create(contrato=contrato, produtos=fixed, valor='100.00')
        screenshot_dir = '/tmp/gestao-produtos-e2e'
        Path(screenshot_dir).mkdir(exist_ok=True)
        env = {**os.environ, 'E2E_BASE_URL': self.live_server_url, 'E2E_USERNAME': editor.username,
               'E2E_PASSWORD': password, 'E2E_READER_USERNAME': reader.username,
               'E2E_SCREENSHOT_DIR': screenshot_dir,
               'PLAYWRIGHT_BROWSERS_PATH': os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/tmp/gestao-playwright')}
        result = subprocess.run(['node_modules/.bin/playwright', 'test', 'produtos.spec.ts'], cwd=settings.BASE_DIR, env=env, timeout=180)
        self.assertEqual(result.returncode, 0)
