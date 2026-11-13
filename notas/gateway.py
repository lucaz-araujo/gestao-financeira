"""Fronteira do provedor NFS-e; nenhuma transmissão acontece ao importar o módulo."""
from datetime import datetime, timezone as dt_timezone
import importlib
from pathlib import Path
import shutil
from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from configambiente.models import Ambiente
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree


class FiscalConfigurationError(Exception):
    pass


def certificate_path(conf):
    if not conf.certificado:
        return None
    try:
        from configambiente.storage import certificate_root
        base = Path(settings.BASE_DIR).resolve()
        private = certificate_root()
        media = Path(settings.MEDIA_ROOT).resolve()
        candidates = [Path(conf.certificado.path), media / str(conf.certificado), base / str(conf.certificado)]
        return next((p.resolve() for p in candidates if any(p.resolve().is_relative_to(root) for root in (private,base,media)) and p.is_file()), None)
    except (OSError, ValueError, SuspiciousFileOperation):
        return None


def fiscal_status(empresa_id):
    conf = Ambiente.objects.filter(empresa_id=empresa_id).first()
    issues = []
    if conf is None:
        return {'disponivel': False, 'homologacao': None, 'pendencias': ['Configure o ambiente fiscal desta empresa.']}
    for module in ('pyxb', 'suds', 'pynfe.processamento.autorizador_nfse', 'pynfe.utils.nfse.speedgov._tipos'):
        try:
            importlib.import_module(module)
        except Exception:
            issues.append('Uma dependência do integrador fiscal não está disponível.')
            break
    if not shutil.which('xmlsec1'):
        issues.append('O assinador de documentos fiscais não está disponível.')
    path = certificate_path(conf)
    if path is None:
        issues.append('O certificado digital não está disponível neste ambiente.')
    else:
        try:
            key, cert, _ = pkcs12.load_key_and_certificates(path.read_bytes(), conf.senha.encode() if conf.senha else None)
            now = datetime.now(dt_timezone.utc)
            if key is None or cert is None or not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
                issues.append('O certificado digital está fora da validade ou incompleto.')
        except Exception:
            issues.append('Não foi possível abrir o certificado digital configurado.')
    if not conf.empresa.cnpj or not conf.empresa.inscricao_municipal:
        issues.append('Complete o CNPJ e a inscrição municipal da empresa.')
    return {'disponivel': not issues, 'homologacao': conf.homologacao, 'pendencias': issues}


class LegacyNfseGateway:
    def check(self, nota):
        status = fiscal_status(nota.empresa_id)
        if not status['disponivel']:
            raise FiscalConfigurationError(' '.join(status['pendencias']))

    def execute(self, nota, acao):
        from configambiente.nfse import Nfse
        client = Nfse(nota)
        if acao == 'emitir':
            return client.EnviarNfse()
        if acao == 'cancelar':
            return client.CancelarNfse(nota)
        if acao == 'consultar_lote':
            return client.ConsultaSituacaoLote(nota)
        if nota.protocolo_envio:
            return client.ConsultaLoteNfse(nota)
        return client.ConsultaNfse(nota) if nota.numero else client.ConsultaRps(nota)


def local(element):
    return etree.QName(element).localname


def element_text(element, name):
    return next(((e.text or '').strip() for e in element.iter() if local(e) == name), '')


def parse_response(xml, nota, acao):
    if not isinstance(xml, (bytes, str)):
        raise ValueError('Resposta fiscal não reconhecida.')
    raw = xml.encode() if isinstance(xml, str) else xml
    if len(raw) > 2_000_000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('Resposta fiscal inválida.')
    root = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True, remove_comments=True, remove_pis=True))
    if any(local(e) == 'Fault' for e in root.iter()):
        raise ValueError('Falha no serviço fiscal.')
    messages = [{'codigo': element_text(e, 'Codigo'), 'mensagem': element_text(e, 'Mensagem'), 'correcao': element_text(e, 'Correcao')}
                for e in root.iter() if local(e) == 'MensagemRetorno']
    result = {'mensagens': messages, 'rejeitada': bool(messages), 'autorizada': False, 'cancelada': False}
    if messages:
        return result
    invoices = [e for e in root.iter() if local(e) == 'InfNfse']
    if invoices:
        matches = [e for e in invoices if element_text(e, 'Numero') == (nota.numero or '') or any(local(r) == 'IdentificacaoRps' and element_text(r, 'Numero') == str(nota.numero_rps) for r in e.iter())]
        if len(matches) != 1:
            raise ValueError('A resposta não identifica uma única nota para o RPS.')
        invoice = matches[0]
        rps = [element_text(r, 'Numero') for r in invoice.iter() if local(r) == 'IdentificacaoRps']
        if rps and nota.numero_rps is not None and rps != [str(nota.numero_rps)]:
            raise ValueError('A resposta pertence a outro RPS.')
        number, code = element_text(invoice, 'Numero'), element_text(invoice, 'CodigoVerificacao')
        if not number or not code or (nota.numero and nota.protocolo_recebimento and nota.numero != number):
            raise ValueError('A resposta fiscal não corresponde à nota.')
        result.update(autorizada=True, numero=number, codigo_verificacao=code, data_emissao=element_text(invoice, 'DataEmissao'))
    protocol = element_text(root, 'Protocolo')
    batch = element_text(root, 'NumeroLote')
    if batch and nota.numero_lote is not None and batch != str(nota.numero_lote):
        raise ValueError('A resposta pertence a outro lote.')
    if protocol and acao != 'cancelar' and nota.protocolo_envio and protocol != nota.protocolo_envio:
        raise ValueError('A resposta pertence a outro protocolo.')
    if protocol:
        result.update(protocolo=protocol, data_recebimento=element_text(root, 'DataRecebimento'))
    cancellation = next((e for e in root.iter() if local(e) in ('Confirmacao', 'InfConfirmacaoCancelamento')), None)
    if cancellation is not None:
        number = element_text(cancellation, 'Numero')
        if not number or number != nota.numero:
            raise ValueError('O cancelamento pertence a outra nota.')
        success = element_text(cancellation, 'Sucesso').lower()
        if success not in ('true', '1', 'false', '0'):
            raise ValueError('A resposta não confirma o sucesso do cancelamento.')
        if success in ('false', '0'):
            result.update(rejeitada=True, mensagens=[{'codigo': 'CANCELAMENTO_NAO_CONFIRMADO', 'mensagem': 'O provedor não confirmou sucesso no cancelamento.', 'correcao': ''}])
        else:
            result.update(cancelada=True, data_cancelamento=element_text(cancellation, 'DataHora'))
    situation = element_text(root, 'Situacao')
    if situation:
        result['situacao_lote'] = situation
    if result['rejeitada']:
        return result
    if not result['autorizada'] and not result['cancelada'] and not protocol and not situation:
        raise ValueError('A resposta não confirma resultado fiscal.')
    return result
