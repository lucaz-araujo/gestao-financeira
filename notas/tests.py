from datetime import timedelta
from decimal import Decimal
import uuid
from unittest.mock import Mock, patch
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from clientes.models import Cliente, Uf, Municipio
from empresa.models import Empresa
from contratos.models import Contrato
from configambiente.models import Ambiente
from financeiro.models import DocReceita, RecReceita
from usuario.models import Usuario
from .models import Nota, OperacaoFiscal
from .gateway import parse_response, FiscalConfigurationError
from .mailing import public_path


def authorization(nota):
    return f'<Resposta><ListaNfse><CompNfse><Nfse><InfNfse><Numero>123</Numero><CodigoVerificacao>VERIFICADO</CodigoVerificacao><IdentificacaoRps><Numero>{nota.numero_rps}</Numero></IdentificacaoRps><DataEmissao>2026-11-01T10:00:00-03:00</DataEmissao></InfNfse></Nfse></CompNfse></ListaNfse></Resposta>'


class NotaAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.uf = Uf.objects.create(sigla='CE', descricao='Ceará')
        cls.city = Municipio.objects.create(uf=cls.uf, codigo_ibge='2304400', descricao='Fortaleza')
        cls.company = Empresa.objects.create(cnpj='11.222.333/0001-81', razao='Empresa A', inscricao_municipal='123', cidade=cls.city, uf=cls.uf)
        cls.other = Empresa.objects.create(cnpj='2', razao='Empresa B')
        cls.customer = Cliente.objects.create(empresa=cls.company, instituicao='Cliente A', cnpj='11.222.333/0001-81',
            endereco='Rua A', numero='1', bairro='Centro', cep='60000000', cidade=cls.city, uf=cls.uf, resp_email='cliente@example.test')
        cls.foreign_customer = Cliente.objects.create(empresa=cls.other, instituicao='Cliente B')
        cls.contract = Contrato.objects.create(empresa=cls.company, cliente=cls.customer, numero='001', valor_bruto='100.10',
            ativo=True, emitirnota=True, objeto='Serviços MMMM/YYYY', prestacao_municipio=True)
        cls.foreign_contract = Contrato.objects.create(empresa=cls.other, cliente=cls.foreign_customer)
        cls.conf = Ambiente.objects.create(empresa=cls.company, descricao='Teste', certificado='inexistente.pfx', senha='', aliquota_iss=5)
        cls.user = Usuario.objects.create_user(username='notas_test', password='test')
        cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='notas'))
        cls.user.user_permissions.add(Permission.objects.get(content_type__app_label='financeiro', codename='add_docreceita'))
        cls.note = Nota.objects.create(empresa=cls.company, contrato=cls.contract, dt_data_emissao=timezone.now(), competencia=11,
            exercicio=2026, valor_bruto='100.10', imposto='5.01', aliq_imposto='5', valor_liquido='100.10',
            texto_nota='Serviços', cidade=cls.city, uf=cls.uf)
        cls.foreign_note = Nota.objects.create(empresa=cls.other, contrato=cls.foreign_contract, dt_data_emissao=timezone.now(), competencia=11, exercicio=2026)

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(self.user)), HTTP_X_EMPRESA_ID=str(self.company.pk))
        self.url = '/notas/api/notas/'
        self.path = f'{self.url}{self.note.pk}/'
        self.gateway = Mock()
        self.gateway.execute.return_value = '<Resposta><NumeroLote>1</NumeroLote><Protocolo>P1</Protocolo></Resposta>'
        self.patcher = patch('notas.services.get_gateway', return_value=self.gateway)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def payload(self, **changes):
        return {**{'contrato': self.contract.pk, 'competencia': 12, 'exercicio': 2026, 'dt_data_emissao': timezone.now().isoformat(),
            'valor_bruto': '100.10', 'imposto': '5.01', 'aliq_imposto': '5', 'valor_liquido': '100.10',
            'texto_nota': 'Serviços', 'cidade': self.city.pk, 'uf': self.uf.pk}, **changes}

    def post(self, action, **body):
        return self.client.post(self.path + action + '/', {'confirmar': True, **body}, format='json')

    def authorized(self):
        Nota.objects.filter(pk=self.note.pk).update(numero='123', numero_rps=1, numero_lote=1, protocolo_envio='P1', protocolo_recebimento='VERIFICADO')
        self.note.refresh_from_db()

    def test_requires_auth_company_and_permissions(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid')
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(self.user)))
        self.assertEqual(self.client.get(self.url).status_code, 400)
        self.assertEqual(self.client.get(self.url, {'empresa': self.other.pk}).status_code, 403)

    def test_company_and_uf_scope(self):
        self.assertEqual(self.client.get(self.url).data['count'], 1)
        for method in ('get', 'patch', 'delete'):
            self.assertEqual(getattr(self.client, method)(f'{self.url}{self.foreign_note.pk}/', {}, format='json').status_code, 404)
        self.assertEqual(self.client.post(self.url, self.payload(contrato=self.foreign_contract.pk), format='json').status_code, 400)
        other_uf = Uf.objects.create(sigla='PI', descricao='Piauí')
        self.user.uf = other_uf
        self.user.save()
        self.assertEqual(self.client.get(self.url).data['count'], 0)
        self.assertEqual(self.client.get(self.url + 'opcoes/').data['count'], 0)

    def test_create_draft_ignores_forged_provider_fields(self):
        response = self.client.post(self.url, self.payload(empresa=self.other.pk, protocolo_recebimento='FORJADO', ja_enviou_NFSE=True, numero_rps=900), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        note = Nota.objects.get(pk=response.data['id'])
        self.assertEqual(note.empresa_id, self.company.pk)
        self.assertIsNone(note.protocolo_recebimento)
        self.assertIsNone(note.numero_rps)
        self.assertFalse(note.ja_enviou_NFSE)
        self.assertEqual(note.exercicio, 2026)

    def test_validation_and_safe_update(self):
        for change in ({'competencia': 13}, {'exercicio': 0}, {'aliq_imposto': '101'}, {'valor_bruto': '-1'}, {'imposto': '0.001'}, {'texto_nota': ''}):
            self.assertEqual(self.client.post(self.url, self.payload(**change), format='json').status_code, 400, change)
        other_uf = Uf.objects.create(sigla='PI', descricao='Piauí')
        self.assertEqual(self.client.patch(self.path, {'uf': other_uf.pk}, format='json').status_code, 400)
        response = self.client.patch(self.path, {'texto_nota': 'Alterado'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['valor_liquido'], '100.10')

    def test_edit_delete_only_pristine_drafts(self):
        self.authorized()
        self.assertEqual(self.client.patch(self.path, {'texto_nota': 'Alterado'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(self.path).status_code, 409)
        Nota.objects.filter(pk=self.note.pk).update(protocolo_recebimento=None, protocolo_envio=None, numero_rps=None, numero_lote=None, numero=None)
        self.assertEqual(self.client.delete(self.path).status_code, 204)

    def test_generate_idempotent_and_no_counter_reservation(self):
        data = {'contratos': [self.contract.pk], 'competencia': 12, 'exercicio': 2026, 'decimo_terceiro': True}
        for created in (True, False):
            response = self.client.post(self.url + 'gerar/', data, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            row = response.data['results'][0]
            self.assertEqual(row['criada'], created)
            self.assertEqual(row['valor_bruto'], '200.20')
            self.assertEqual(row['imposto'], '10.01')
            self.assertIn('DEZEMBRO/2026', row['texto_nota'])
            self.assertIsNone(row['numero_rps'])
        self.conf.refresh_from_db()
        self.assertEqual(str(self.conf.numero_rps), '0')
        data['decimo_terceiro'] = False
        self.assertEqual(self.client.post(self.url + 'gerar/', data, format='json').status_code, 409)
        self.gateway.execute.assert_not_called()

    def test_generation_atomic_and_scoped(self):
        invalid = Contrato.objects.create(empresa=self.company, cliente=self.customer, ativo=False)
        data = {'contratos': [self.contract.pk, invalid.pk], 'competencia': 12, 'exercicio': 2026}
        self.assertEqual(self.client.post(self.url + 'gerar/', data, format='json').status_code, 400)
        self.assertFalse(Nota.objects.filter(competencia=12).exists())
        data['contratos'] = [self.foreign_contract.pk]
        self.assertEqual(self.client.post(self.url + 'gerar/', data, format='json').status_code, 400)

    def test_external_requires_confirmation_and_post(self):
        self.assertEqual(self.client.get(self.path + 'emitir/').status_code, 405)
        self.assertEqual(self.client.post(self.path + 'emitir/', {}, format='json').status_code, 400)
        self.assertEqual(self.post('emitir', confirmar=False).status_code, 400)
        self.gateway.execute.assert_not_called()

    def test_emission_idempotency_protocol_and_authorization(self):
        key = str(uuid.uuid4())
        for _ in range(2):
            response = self.client.post(self.path + 'emitir/', {'confirmar': True}, format='json', HTTP_IDEMPOTENCY_KEY=key)
            self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.gateway.execute.call_count, 1)
        self.note.refresh_from_db()
        self.assertEqual(self.note.protocolo_envio, 'P1')
        self.assertIsNone(self.note.protocolo_recebimento)
        self.assertEqual(self.note.numero_rps, 1)
        self.assertEqual(self.post('emitir').status_code, 409)
        self.gateway.execute.side_effect = lambda note, action: authorization(note)
        self.assertEqual(self.post('consultar').status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.estado_fiscal, 'autorizada')
        self.assertEqual(self.note.numero, '123')

    def test_reservation_never_reuses_historical_sequence(self):
        Nota.objects.create(empresa=self.company, contrato=self.contract, dt_data_emissao=timezone.now(),
            competencia=1, exercicio=2026, numero_rps=40, numero_lote=50)
        self.gateway.execute.return_value = '<Resposta><NumeroLote>51</NumeroLote><Protocolo>P1</Protocolo></Resposta>'
        self.assertEqual(self.post('emitir').status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.numero_lote, 51)
        self.assertEqual(self.note.numero_rps, 41)

    def test_missing_configuration_does_not_reserve_or_transmit(self):
        self.gateway.check.side_effect = FiscalConfigurationError('Certificado ausente.')
        self.assertEqual(self.post('emitir').status_code, 503)
        self.assertFalse(OperacaoFiscal.objects.exists())
        self.note.refresh_from_db()
        self.assertIsNone(self.note.numero_rps)
        self.gateway.execute.assert_not_called()

    def test_invalid_customer_does_not_transmit(self):
        Cliente.objects.filter(pk=self.customer.pk).update(cnpj='invalid')
        self.assertEqual(self.post('emitir').status_code, 400)
        self.gateway.execute.assert_not_called()

    def test_uncertain_emission_blocks_retry_until_authorized_query(self):
        self.gateway.execute.side_effect = TimeoutError()
        self.assertEqual(self.post('emitir').status_code, 502)
        self.assertEqual(self.post('emitir').status_code, 409)
        self.note.refresh_from_db()
        self.assertEqual(self.note.estado_fiscal, 'incerta')
        # O RPS reservado permite conciliar mesmo sem protocolo recebido.
        self.gateway.execute.side_effect = lambda note, action: authorization(note)
        self.assertEqual(self.post('consultar').status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.estado_fiscal, 'autorizada')
        self.assertFalse(self.note.operacoes.filter(estado='incerta').exists())

    def test_business_rejection_does_not_authorize(self):
        self.gateway.execute.return_value = '<Resposta><ListaMensagemRetorno><MensagemRetorno><Codigo>E1</Codigo><Mensagem>Dados inválidos</Mensagem></MensagemRetorno></ListaMensagemRetorno></Resposta>'
        response = self.post('emitir')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['operacao']['estado'], 'falha')
        self.note.refresh_from_db()
        self.assertIsNone(self.note.protocolo_recebimento)
        self.assertEqual(self.client.patch(self.path, {'texto_nota': 'Alterar'}, format='json').status_code, 400)

    def test_cancel_only_confirmed_and_does_not_replace_emission_protocol(self):
        self.authorized()
        self.gateway.execute.return_value = '<Resposta><Protocolo>CANCEL1</Protocolo></Resposta>'
        self.assertEqual(self.post('cancelar', justificativa='Correção').status_code, 502)
        self.note.refresh_from_db()
        self.assertIsNone(self.note.cancelada_em)
        self.assertEqual(self.note.protocolo_envio, 'P1')
        self.gateway.execute.return_value = '<Resposta><Cancelamento><Confirmacao><InfConfirmacaoCancelamento><Sucesso>true</Sucesso><IdentificacaoNfse><Numero>123</Numero></IdentificacaoNfse><DataHora>2026-11-03T12:00:00-03:00</DataHora></InfConfirmacaoCancelamento></Confirmacao></Cancelamento></Resposta>'
        self.assertEqual(self.post('consultar').status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.estado_fiscal, 'cancelada')
        self.assertFalse(self.note.operacoes.filter(estado='incerta').exists())
        self.assertEqual(self.post('financeiro').status_code, 409)

    def test_cancellation_requires_explicit_success(self):
        self.authorized()
        self.gateway.execute.return_value = '<Resposta><Confirmacao><Numero>123</Numero><InfConfirmacaoCancelamento><Sucesso>false</Sucesso></InfConfirmacaoCancelamento></Confirmacao></Resposta>'
        self.assertEqual(self.post('cancelar', justificativa='Teste').status_code, 400)
        self.note.refresh_from_db()
        self.assertIsNone(self.note.cancelada_em)
        self.assertEqual(self.note.protocolo_envio, 'P1')

    def test_financial_generation_idempotent_preserves_receipts(self):
        self.assertEqual(self.post('financeiro').status_code, 409)
        self.authorized()
        first = self.post('financeiro')
        self.assertEqual(first.status_code, 201, first.data)
        doc = DocReceita.objects.get(pk=first.data['id'])
        doc.valor_recebido = Decimal('50.00'); doc.situacao = 'P'; doc.save()
        payment = RecReceita.objects.create(receita=doc, dt_pagamento='2026-11-03', valor='50', user_registro=self.user)
        self.assertEqual(self.post('financeiro').status_code, 200)
        doc.refresh_from_db()
        self.assertEqual(doc.valor_recebido, Decimal('50'))
        self.assertTrue(RecReceita.objects.filter(pk=payment.pk).exists())
        self.assertTrue(self.note.ja_pago())
        self.assertEqual(self.post('cancelar', justificativa='Teste').status_code, 409)
        self.gateway.execute.assert_not_called()

    def test_legacy_reserved_rps_requires_reconciliation(self):
        Nota.objects.filter(pk=self.note.pk).update(numero_rps=10, numero_lote=10)
        response = self.client.get(self.url, {'estado': 'incerta'})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['estado_fiscal'], 'incerta')
        self.assertEqual(self.post('emitir').status_code, 409)
        self.assertEqual(self.client.delete(self.path).status_code, 409)
        self.assertEqual(self.client.patch(self.path, {'texto_nota': 'Alterado'}, format='json').status_code, 400)
        self.gateway.execute.assert_not_called()
        self.gateway.execute.side_effect = lambda note, action: authorization(note)
        self.assertEqual(self.post('consultar').status_code, 200)
        self.note.refresh_from_db()
        self.assertEqual(self.note.estado_fiscal, 'autorizada')

    def test_pending_operation_blocks_financial_generation(self):
        self.authorized()
        OperacaoFiscal.objects.create(nota=self.note, usuario=self.user, acao='cancelar', estado='incerta', chave=uuid.uuid4())
        self.assertEqual(self.post('financeiro').status_code, 409)
        self.assertFalse(DocReceita.objects.exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PUBLIC_APP_URL='https://example.test')
    def test_email_uses_local_backend_and_signed_public_links(self):
        self.authorized()
        response = self.post('email')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['cliente@example.test'])
        self.assertIn('/notas/publica/', mail.outbox[0].body)
        self.note.refresh_from_db()
        self.assertTrue(self.note.ja_enviou)
        self.gateway.execute.assert_not_called()
        response = self.client.get(self.path + 'link_publico/')
        from urllib.parse import urlparse
        path = urlparse(response.data['url']).path
        public = APIClient()
        self.assertContains(public.get(path), 'VERIFICADO')
        self.assertEqual(public.get('/notas/nf/123456789/').status_code, 410)
        self.assertEqual(public.get(path.replace('publica/', 'publica/tampered')).status_code, 410)
        with override_settings(NOTAS_PUBLIC_LINK_MAX_AGE=-1):
            self.assertEqual(public.get(path).status_code, 410)

    def test_public_link_cannot_expose_drafts_or_other_company(self):
        self.assertEqual(APIClient().get(public_path(self.note)).status_code, 410)
        self.authorized()
        self.foreign_note.protocolo_recebimento = 'OUTRA'; self.foreign_note.save()
        response = APIClient().get(public_path(self.note, client_list=True))
        self.assertNotContains(response, 'OUTRA')
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_reports_filters_and_totals(self):
        response = self.client.get(self.url + 'relatorio/', {'dt_inicial': timezone.localdate().isoformat(), 'dt_final': timezone.localdate().isoformat()})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['valor_total'], '100.10')
        self.assertEqual(response.data['total_imposto'], '5.01')
        self.assertEqual(self.client.get(self.url, {'estado': 'rascunho'}).data['count'], 1)
        for data in ({'cliente': 'invalid'}, {'estado': 'invalido'}, {'dt_inicial': '2026-01-01'}, {'email_enviado': 'nao'}):
            self.assertEqual(self.client.get(self.url, data).status_code, 400)

    def test_readonly_and_csrf_permissions(self):
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='notas', codename='view_nota'))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.payload(), format='json').status_code, 403)
        for action in ('emitir', 'cancelar', 'email', 'financeiro'):
            self.assertEqual(self.post(action).status_code, 403)
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.path + 'consultar_lote/', {'confirmar': True}, format='json').status_code, 403)

    def test_parser_rejects_foreign_documents_entities_and_empty_responses(self):
        self.authorized()
        for xml in ('<r/>', '<!DOCTYPE foo [<!ENTITY x SYSTEM "file:///etc/passwd">]><r>&x;</r>',
            '<r><InfNfse><Numero>999</Numero><CodigoVerificacao>X</CodigoVerificacao><IdentificacaoRps><Numero>999</Numero></IdentificacaoRps></InfNfse></r>',
            '<r><NumeroLote>999</NumeroLote><Protocolo>P1</Protocolo></r>', '<r><Protocolo>OUTRO</Protocolo></r>'):
            with self.assertRaises(ValueError): parse_response(xml, self.note, 'consultar')


class FiscalAdapterTests(TestCase):
    def test_synthetic_certificate_signing_and_xml_serialization_offline(self):
        from pathlib import Path
        import tempfile
        import subprocess
        from datetime import datetime, timezone as dt_timezone
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives.serialization import pkcs12
        from lxml import etree
        from pynfe.entidades.certificado import CertificadoA1
        from pynfe.processamento.assinatura import AssinaturaA1
        from configambiente.nfse import Nfse
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic local test')])
        now = datetime.now(dt_timezone.utc)
        cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(private_key.public_key()).serial_number(
            x509.random_serial_number()).not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1)).sign(private_key, hashes.SHA256())
        with tempfile.TemporaryDirectory(prefix='notas-cert-test-') as tmp:
            path = Path(tmp) / 'synthetic.pfx'
            path.write_bytes(pkcs12.serialize_key_and_certificates(b'test', private_key, cert, None, serialization.BestAvailableEncryption(b'test')))
            reader = CertificadoA1(str(path))
            key, encoded = reader.separar_arquivo('test')
            self.assertIn(b'PRIVATE KEY', key)
            self.assertTrue(encoded)
            key_path, cert_path = reader.separar_arquivo('test', caminho=True)
            self.assertEqual(Path(key_path).stat().st_mode & 0o777, 0o600)
            from pynfe.utils.https_nfse import HTTPSClientAuthHandler
            connection = HTTPSClientAuthHandler(key_path, cert_path).getConnection('example.test', timeout=5)
            self.assertEqual(connection.timeout, 5)
            self.assertTrue(connection._context.check_hostname)
            connection.close()
            reader.excluir()
            self.assertFalse(Path(key_path).exists())
            first = AssinaturaA1(str(path), 'test', 'speedgov')
            second = AssinaturaA1(str(path), 'test', 'speedgov')
            self.assertNotEqual(first._file('nfse.xml'), second._file('nfse.xml'))
            try:
                signed = first.assinarConsulta('<p:ConsultarNfseEnvio xmlns:p="urn:test"><Numero>1</Numero></p:ConsultarNfseEnvio>')
            except subprocess.CalledProcessError as error:
                self.fail(error.stderr.decode())
            self.assertTrue(etree.fromstring(signed).find('.//{http://www.w3.org/2000/09/xmldsig#}SignatureValue').text)
            import subprocess
            cert_pem = Path(tmp) / 'public.pem'
            cert_pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            query_xml = Path(tmp) / 'query.xml'
            query_xml.write_text(signed)
            subprocess.run(['xmlsec1', '--verify', '--pubkey-cert-pem:gestao-nfse', str(cert_pem), str(query_xml)],
                           check=True, capture_output=True, timeout=30)
            first._tmp.cleanup(); second._tmp.cleanup()
            uf = Uf.objects.create(sigla='CE', descricao='Ceará')
            city = Municipio.objects.create(uf=uf, codigo_ibge='2304400', descricao='Fortaleza')
            company = Empresa.objects.create(cnpj='11.222.333/0001-81', inscricao_municipal='123', razao='Emissor teste')
            Ambiente.objects.create(empresa=company, descricao='Teste', certificado='synthetic.pfx', senha='test', aliquota_iss=5)
            customer = Cliente.objects.create(empresa=company, instituicao='Tomador teste', cnpj='11.222.333/0001-81',
                endereco='Rua teste', numero='1', bairro='Centro', cep='60000000', cidade=city, uf=uf)
            contract = Contrato.objects.create(empresa=company, cliente=customer)
            note = Nota.objects.create(empresa=company, contrato=contract, dt_data_emissao=timezone.now(), competencia=11, exercicio=2026,
                valor_bruto=100, valor_liquido=100, aliq_imposto=5, imposto=5, texto_nota='Teste local', cidade=city, uf=uf, numero_rps=1, numero_lote=1)
            with patch('notas.gateway.certificate_path', return_value=path), patch('configambiente.nfse.ComunicacaoNfse') as transport:
                adapter = Nfse(note)
                other_adapter = Nfse(note)
                self.assertIsNot(adapter.cliente, other_adapter.cliente)
                adapter.EnviarNfse()
                emitted_xml = transport.return_value.enviar_lote.call_args.args[0]
                note.numero = '123'
                adapter.ConsultaNfse(note)
                adapter.ConsultaRps(note)
                note.protocolo_envio = 'P1'
                adapter.ConsultaLoteNfse(note)
                adapter.ConsultaSituacaoLote(note)
                adapter.CancelarNfse(note)
                for method, schema_name in [('consultar', 'consultar_nfse'), ('consultar_rps', 'consultar_nfse_rps'),
                                           ('consultar_lote', 'consultar_lote_rps'), ('consultar_situacao_lote', 'consultar_situacao_lote_rps'),
                                           ]:
                    from django.conf import settings
                    document = getattr(transport.return_value, method).call_args.args[0]
                    root = Path(settings.BASE_DIR) / 'pynfe/data/XSDs/NFS-e/Speedgov'
                    etree.XMLSchema(etree.parse(str(root / f'servico_{schema_name}_envio_v1.xsd'))).assertValid(etree.fromstring(document))
                    if method == 'consultar_lote':
                        query_xml.write_text(document)
                        subprocess.run(['xmlsec1', '--verify', '--pubkey-cert-pem:gestao-nfse', str(cert_pem), str(query_xml)],
                                       check=True, capture_output=True, timeout=30)
                cancel_xml = transport.return_value.cancelar.call_args.args[0]
                self.assertEqual(etree.QName(etree.fromstring(cancel_xml)).namespace, 'http://ws.speedgov.com.br/cancelar_nfse_envio')
                self.assertIn('11222333000181', cancel_xml)
                self.assertIn('123', cancel_xml)
                self.assertIn('11222333000181', emitted_xml)
                self.assertIn('SignatureValue', emitted_xml)
                from django.conf import settings
                schema = etree.XMLSchema(etree.parse(str(Path(settings.BASE_DIR) / 'pynfe/data/XSDs/NFS-e/Speedgov/servico_enviar_lote_rps_envio_v1.xsd')))
                schema.assertValid(etree.fromstring(emitted_xml))
                signed_batch = Path(tmp) / 'batch.xml'
                signed_batch.write_text(emitted_xml)
                for tag, node in [('InfRps', '//*[local-name()="Rps"]/*[local-name()="Signature"]'),
                                  ('LoteRps', '/*/*[local-name()="Signature"]')]:
                    result = subprocess.run(['xmlsec1', '--verify', '--pubkey-cert-pem:gestao-nfse', str(cert_pem),
                                    '--id-attr:Id', tag, '--node-xpath', node, str(signed_batch)], capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 0, tag + ': ' + result.stderr.decode())
                self.assertEqual(len(etree.fromstring(emitted_xml).xpath('//*[local-name()="SignatureValue"]')), 2)
