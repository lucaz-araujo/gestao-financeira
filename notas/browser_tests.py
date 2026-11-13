import os
from pathlib import Path
import secrets
import subprocess
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from clientes.models import Cliente, Uf, Municipio
from configambiente.models import Ambiente
from contratos.models import Contrato
from empresa.models import Empresa
from usuario.models import Usuario
from .models import Nota


class SimulatedGateway:
    def check(self, nota):
        pass

    def execute(self, nota, acao):
        if acao == 'emitir':
            return f'<Resposta><NumeroLote>{nota.numero_lote}</NumeroLote><Protocolo>P{nota.pk}</Protocolo></Resposta>'
        if acao == 'cancelar':
            return f'<Resposta><Confirmacao><InfConfirmacaoCancelamento><Sucesso>true</Sucesso><Numero>{nota.numero}</Numero></InfConfirmacaoCancelamento></Confirmacao></Resposta>'
        return f'<Resposta><InfNfse><Numero>{nota.numero or str(1000 + nota.pk)}</Numero><CodigoVerificacao>TESTE-LOCAL</CodigoVerificacao><IdentificacaoRps><Numero>{nota.numero_rps}</Numero></IdentificacaoRps></InfNfse></Resposta>'


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PUBLIC_APP_URL='https://example.test')
class NotaBrowserTests(StaticLiveServerTestCase):
    def test_notes_frontend(self):
        cache.clear()
        uf = Uf.objects.create(sigla='CE', descricao='Ceará')
        city = Municipio.objects.create(uf=uf, codigo_ibge='2304400', descricao='Fortaleza')
        company = Empresa.objects.create(cnpj='11.222.333/0001-81', razao='Empresa Alfa', inscricao_municipal='1', cidade=city, uf=uf)
        other = Empresa.objects.create(cnpj='2', razao='Empresa Beta')
        customer = Cliente.objects.create(empresa=company, instituicao='Cliente Alfa', cnpj='11.222.333/0001-81', uf=uf, cidade=city,
            endereco='Rua A', numero='1', bairro='Centro', cep='60000000', resp_email='cliente@example.test')
        contract = Contrato.objects.create(empresa=company, cliente=customer, numero='CON-ALFA', ativo=True, emitirnota=True,
            valor_bruto=100, objeto='Serviços MMMM/YYYY', prestacao_municipio=True)
        Ambiente.objects.create(empresa=company, descricao='Teste isolado', certificado='ausente.pfx', aliquota_iss=5, senha='')
        Nota.objects.create(empresa=company, contrato=contract, numero='9000', protocolo_recebimento='TESTE-LOCAL',
            dt_data_emissao=timezone.now(), competencia=1, exercicio=2026, valor_bruto=100, valor_liquido=100, imposto=5, aliq_imposto=5, texto_nota='Cancelamento de teste')
        other_customer = Cliente.objects.create(empresa=other, instituicao='Cliente Beta')
        other_contract = Contrato.objects.create(empresa=other, cliente=other_customer)
        Nota.objects.create(empresa=other, contrato=other_contract, numero='BETA', dt_data_emissao=timezone.now(), competencia=1, exercicio=2026, valor_liquido=999)
        password = secrets.token_urlsafe(24)
        user = Usuario.objects.create_user(username='notas_browser', email='notas-browser@example.test', password=password)
        user.empresas.add(company, other)
        user.user_permissions.set(Permission.objects.filter(content_type__app_label='notas'))
        user.user_permissions.add(Permission.objects.get(content_type__app_label='financeiro', codename='add_docreceita'))
        reader = Usuario.objects.create_user(username='notas_reader', email='notas-reader@example.test', password=password)
        reader.empresas.add(company)
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='notas', codename='view_nota'))
        screenshots = '/tmp/gestao-notas-e2e'
        Path(screenshots).mkdir(exist_ok=True)
        env = {**os.environ, 'E2E_BASE_URL': self.live_server_url, 'E2E_USERNAME': user.username, 'E2E_READER_USERNAME': reader.username,
            'E2E_PASSWORD': password, 'E2E_SCREENSHOT_DIR': screenshots, 'PLAYWRIGHT_BROWSERS_PATH': '/tmp/gestao-playwright'}
        with patch('notas.services.get_gateway', return_value=SimulatedGateway()), patch('notas.views.fiscal_status', return_value={
            'disponivel': True, 'homologacao': True, 'pendencias': []}):
            result = subprocess.run(['node_modules/.bin/playwright', 'test', 'notas.spec.ts'], cwd=settings.BASE_DIR, env=env, timeout=240)
        self.assertEqual(result.returncode, 0)
