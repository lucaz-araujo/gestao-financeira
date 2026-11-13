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
from empresa.models import Empresa
from usuario.models import Usuario
from financeiro.models import FechamentoCaixa
from contabil.models import PlanoContas
from .models import Banco, Conta, Movimento


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class ContaBrowserTests(StaticLiveServerTestCase):
    def test_banking_frontend(self):
        cache.clear()
        company = Empresa.objects.create(cnpj='1', razao='Empresa Alfa')
        other = Empresa.objects.create(cnpj='2', razao='Empresa Beta')
        password = secrets.token_urlsafe(24)
        user = Usuario.objects.create_user(username='conta_browser', email='conta-browser@example.test', password=password)
        user.empresas.add(company, other)
        user.user_permissions.set(Permission.objects.filter(content_type__app_label='conta'))
        reader = Usuario.objects.create_user(username='conta_reader', email='conta-reader@example.test', password=password)
        reader.empresas.add(company)
        reader.user_permissions.set(Permission.objects.filter(content_type__app_label='conta', codename__startswith='view_'))
        bank = Banco.objects.create(codigo='001', nome='Banco A')
        accounts = []
        for index, name in enumerate(['Origem', 'Destino', 'Fechada']):
            accounts.append(Conta.objects.create(empresa=company, banco=bank, agencia='0001', dv_agencia='X', numeroconta=f'00{index+1}', dv_conta='1', descricao=name))
        Conta.objects.create(empresa=other, banco=bank, agencia='0002', dv_agencia='X', numeroconta='004', descricao='Conta Beta')
        PlanoContas.objects.create(empresa=company, conta='1.1', descricao='Caixa')
        today = timezone.localdate()
        Movimento.objects.create(empresa=company, conta=accounts[0], dt_movimento=today.replace(day=1), tipo_movimento='C', tipo_documento='OUT', valor='10.000', nr_documento='INICIAL', usuario=user)
        FechamentoCaixa.objects.create(empresa=company, conta=accounts[2], data=today, hora=timezone.localtime().time(),
            user_fechamento=user, saldo_anterior=0, saldo=0, receitas=0, despesas=0)
        screenshots = '/tmp/gestao-contas-e2e'; Path(screenshots).mkdir(exist_ok=True)
        env = {**os.environ, 'E2E_BASE_URL': self.live_server_url, 'E2E_USERNAME': user.username, 'E2E_READER_USERNAME': reader.username,
            'E2E_PASSWORD': password, 'E2E_SCREENSHOT_DIR': screenshots, 'PLAYWRIGHT_BROWSERS_PATH': '/tmp/gestao-playwright'}
        result = subprocess.run(['node_modules/.bin/playwright', 'test', 'conta.spec.ts'], cwd=settings.BASE_DIR, env=env, timeout=300)
        self.assertEqual(result.returncode, 0)
