import hashlib
from datetime import date
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import APIException
from clientes.models import Cliente, Liberacao, LiberacaoDatas
from chaves.models import ChaveServico
from financeiro.models import Configuracao
from notas.models import Nota
from usuario.models import Usuario
from .serializers import EntidadePublicaSerializer, NotaLegadaSerializer, LiberacaoLegadaSerializer, ChaveLegadaSerializer


class IntegracaoIndisponivel(APIException):
    status_code = 503
    default_detail = 'Integração indisponível. Contate o administrador.'


def digest(value, sha256=False):
    try:
        raw = value.encode('ascii')
    except (UnicodeEncodeError, AttributeError):
        raise IntegracaoIndisponivel()
    return (hashlib.sha256(raw) if sha256 else hashlib.md5(raw)).hexdigest()


def autenticar(data, kind):
    if kind == 'servico':
        payload = data['servico'] + data['cnpj'] + data['competencia']
    else:
        payload = data['codigo_layout'] + data['codigo']
        payload += data['tipo'] if kind == 'transparencia' else data['competencia']
    payload += settings.API_SECRET_KEY
    if kind == 'web':
        payload += timezone.localdate().strftime('%d%m%Y')
    expected = digest(payload, sha256=kind == 'web')
    supplied = data['key'] if kind == 'web' else data['key'].lower()
    return constant_time_compare(supplied, expected)


def cliente_unico(data, kind, lock=False):
    if kind == 'servico':
        qs = Cliente.objects.filter(cnpj=data['cnpj'])
    else:
        # O endpoint web histórico inverte os campos de consulta; a assinatura
        # mantém a ordem codigo_layout + codigo em todos os consumidores.
        code, layout = (data['codigo_layout'], data['codigo']) if kind == 'web' else (data['codigo'], data['codigo_layout'])
        qs = Cliente.objects.filter(codigoentidade=code, codigolayout=layout)
    if lock:
        qs = qs.select_for_update(of=('self',))
    rows = list(qs.select_related('parceiro').order_by('pk')[:2])
    if len(rows) != 1:
        return None
    customer = rows[0]
    return customer if customer.ativo and not customer.desativar and customer.empresa_id else None


def notas_cliente(customer, active_only=True):
    qs = Nota.objects.filter(contrato__cliente=customer, empresa_id=customer.empresa_id, contrato__empresa_id=customer.empresa_id)
    return qs.filter(contrato__ativo=True) if active_only else qs


def periodo(data):
    value = data['competencia']
    return '12' + value if len(value) == 4 else value


def bloqueios(customer, comp):
    point = date(int(comp[2:]), int(comp[:2]), 1)
    return LiberacaoDatas.objects.filter(cliente=customer, dt_ate__lte=point, dt_aparte__gte=point).order_by('pk')


def configuracao():
    config = Configuracao.objects.filter(pk=1).first()
    if config is None or config.liberaquantnotasabertas < 0:
        raise IntegracaoIndisponivel()
    return config


def resposta_liberacao(record, customer, comp, dated, created=False):
    data = dict(LiberacaoLegadaSerializer(record).data)
    if created:
        data['data_liberacao'] = timezone.localdate().isoformat()
    payload = customer.codigoentidade + customer.codigolayout + comp + 'sucesso' + settings.API_SECRET_KEY
    if dated:
        payload += timezone.localdate().strftime('%d%m%Y')
    return {'liberado': True, **data, 'key': digest(payload)}


@transaction.atomic
def liberar(data, transparencia=False):
    customer = cliente_unico(data, 'transparencia' if transparencia else 'delphi', lock=True)
    if customer is None or not customer.gerar_notas:
        return {'liberado': False}
    comp = timezone.localdate().strftime('%m%Y') if transparencia else data['competencia']
    if transparencia:
        flag = 'libera_transparencia' if data['tipo'] == '1' else 'libera_contracheque'
        if not getattr(customer, flag) or any(block.desativar or not block.gerar_notas or not getattr(block, flag) for block in bloqueios(customer, comp)):
            return {'liberado': False}
    config = configuracao()
    notes = notas_cliente(customer)
    unpaid = notes.exclude(docreceitas__situacao='R')
    partner_exempt = customer.parceiro_id and customer.parceiro.empresa_id == customer.empresa_id and not customer.parceiro.excecao
    eligible = bool(partner_exempt or (notes.exists() and unpaid.count() <= config.liberaquantnotasabertas))
    existing = list(Liberacao.objects.filter(cliente=customer, codigo=customer.codigoentidade, codigo_layout=customer.codigolayout,
        competencia=comp[:2], exercicio=int(comp[2:])).select_related('usuario').order_by('pk')[:2])
    if len(existing) > 1:
        return {'liberado': False}
    if existing:
        return resposta_liberacao(existing[0], customer, comp, dated=not eligible)
    if not eligible:
        return {'liberado': False, **({'notas': NotaLegadaSerializer(unpaid.order_by('pk'), many=True).data} if unpaid.exists() else {})}
    actor = Usuario.objects.filter(pk=settings.API_INTEGRATION_USER_ID, is_active=True).first()
    if actor is None or len(customer.codigoentidade) > 4 or len(customer.codigolayout) > 4:
        raise IntegracaoIndisponivel()
    record = Liberacao(cliente=customer, codigo=customer.codigoentidade, codigo_layout=customer.codigolayout,
        competencia=comp[:2], exercicio=int(comp[2:]), usuario=actor, dt_liberacao=timezone.now())
    record.atualizar_chave()
    record.save()
    return resposta_liberacao(record, customer, comp, dated=True, created=True)


def liberar_web(data):
    customer = cliente_unico(data, 'web')
    if customer is None:
        return {'liberado': False}
    config = configuracao()
    notes = notas_cliente(customer, active_only=False).filter(dt_data_pagamento__isnull=True)
    if notes.count() <= config.liberaquantnotasabertas:
        return {'liberado': True}
    return {'liberado': False, 'notas': NotaLegadaSerializer(notes.order_by('pk'), many=True).data}


def liberar_servico(data):
    customer = cliente_unico(data, 'servico')
    if customer is None or customer.parceiro_id is None or customer.parceiro.empresa_id != customer.empresa_id or customer.parceiro.excecao:
        return {'liberado': False}
    records = list(ChaveServico.objects.filter(cliente=customer, competencia=data['competencia'][:2], exercicio=int(data['competencia'][2:]),
        servico__descricao=data['servico'], servico__cliente=customer, servico__empresa_id=customer.empresa_id).select_related('usuario').order_by('pk')[:2])
    if len(records) != 1:
        return {'liberado': False}
    payload = data['servico'] + data['cnpj'] + data['competencia'] + 'sucesso' + settings.API_SECRET_KEY
    return {'liberado': True, **ChaveLegadaSerializer(records[0]).data, 'key': digest(payload)}


def consultar_bloqueio(data):
    customer = cliente_unico(data, 'delphi')
    flags = {'liberabloqueio': 'libera_sistema', 'liberatcm': 'libera_tcm', 'liberapagonline': 'libera_pagonline'}
    if customer is None:
        return {**{name: False for name in flags}, 'error': 'Cliente não cadastrado'}
    blocks = list(bloqueios(customer, periodo(data)))
    if any(block.desativar for block in blocks):
        return {name: False for name in flags}
    return {name: all(getattr(block, field) for block in blocks) if blocks else getattr(customer, field) for name, field in flags.items()}


def entidades_publicas(data):
    rows = Cliente.objects.filter(cidade__codigo_ibge=data['municipio']).order_by().values('cnpj', 'instituicao', 'codigoentidade').distinct().order_by('instituicao', 'cnpj', 'codigoentidade')
    return EntidadePublicaSerializer(rows, many=True).data
