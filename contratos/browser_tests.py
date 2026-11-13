import os
from pathlib import Path
import secrets
import subprocess
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from clientes.models import Cliente, Uf
from empresa.models import Empresa
from notas.models import Nota
from produtos.models import Produto
from usuario.models import Usuario
from .models import Contrato, ContratoProduto, ContratoRenovacao


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class ContratoBrowserTests(StaticLiveServerTestCase):
    def test_contract_frontend(self):
        cache.clear()
        company = Empresa.objects.create(cnpj='1', razao='Empresa Alfa')
        other = Empresa.objects.create(cnpj='2', razao='Empresa Beta')
        uf = Uf.objects.create(sigla='CE', descricao='Ceará')
        cliente = Cliente.objects.create(empresa=company, instituicao='Cliente Alfa', uf=uf, cnpj='11.222.333/0001-81')
        other_client = Cliente.objects.create(empresa=other, instituicao='Cliente Beta')
        product = Produto.objects.create(empresa=company, descricao='Folha de pagamento', sigla='FOLHA', valor='1000.00')
        Produto.objects.create(empresa=other, descricao='Produto Beta', sigla='BETA', valor='999.00')
        contract = Contrato.objects.create(empresa=company, cliente=cliente, numero='COM-NOTA', dia_nota=1,
            dt_data_contrato='2026-01-01', dt_data_final='2026-12-31', exercicio=2026, objeto='Contrato com nota',
            valor_bruto=100, perc_iss=0, perc_irpj=0, valor_iss=0, valor_irpj=0, valor_liquido=100)
        ContratoProduto.objects.create(contrato=contract, produtos=product, valor=100)
        Nota.objects.create(empresa=company, contrato=contract, numero='NF-TESTE', competencia=1, exercicio=2026,
                            dt_data_emissao=timezone.now(), valor_liquido=100)
        Contrato.objects.create(empresa=other, cliente=other_client, numero='BETA', valor_liquido=999)
        password = secrets.token_urlsafe(24)
        user = Usuario.objects.create_user(username='con_browser', email='contract-browser@example.com', password=password)
        user.empresas.add(company, other)
        user.user_permissions.set(Permission.objects.filter(content_type__app_label='contratos', codename__in=['view_contrato', 'add_contrato', 'change_contrato', 'delete_contrato']))
        reader = Usuario.objects.create_user(username='con_reader', email='contract-reader@example.com', password=password)
        reader.empresas.add(company)
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='contratos', codename='view_contrato'))
        screenshots = '/tmp/gestao-contratos-e2e'
        Path(screenshots).mkdir(exist_ok=True)
        env = {**os.environ, 'E2E_BASE_URL': self.live_server_url, 'E2E_USERNAME': user.username,
               'E2E_READER_USERNAME': reader.username, 'E2E_PASSWORD': password, 'E2E_SCREENSHOT_DIR': screenshots,
               'PLAYWRIGHT_BROWSERS_PATH': os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/tmp/gestao-playwright')}
        result = subprocess.run(['node_modules/.bin/playwright', 'test', 'contratos.spec.ts'], cwd=settings.BASE_DIR, env=env, timeout=240)
        self.assertEqual(result.returncode, 0)
