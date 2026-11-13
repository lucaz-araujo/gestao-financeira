"""Casos de uso transacionais; nenhuma operação externa é executada em GET."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import uuid
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from rest_framework import serializers
from rest_framework.exceptions import APIException, ValidationError
from clientes.validador import validar_cnpj
from configambiente.models import Ambiente
from contratos.models import Contrato
from financeiro.models import DocReceita
from .gateway import LegacyNfseGateway, FiscalConfigurationError, parse_response
from .models import Nota, OperacaoFiscal


class NotaConflict(APIException):
    status_code = 409
    default_code = 'conflict'
    default_detail = 'A operação conflita com o histórico da nota.'


class IntegracaoIndisponivel(APIException):
    status_code = 503
    default_detail = 'A integração não está configurada neste ambiente.'


class ResultadoIncerto(APIException):
    status_code = 502
    default_detail = 'Não foi possível confirmar o resultado externo. Consulte o histórico antes de repetir.'


def get_gateway():
    return LegacyNfseGateway()


def parse_provider_datetime(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        date = parse_date(value)
        if date:
            from datetime import datetime, time
            parsed = datetime.combine(date, time.min)
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


@transaction.atomic
def gerar_rascunhos(contratos, competencia, exercicio, decimo_terceiro=False):
    result = []
    for contrato in sorted(contratos, key=lambda c: c.pk):
        contrato = Contrato.objects.select_for_update(of=('self',)).select_related('cliente__cidade', 'cliente__uf', 'empresa__cidade').get(pk=contrato.pk)
        if not contrato.ativo or not contrato.emitirnota or contrato.cliente.desativar or not contrato.cliente.gerar_notas:
            raise ValidationError({'contratos': f'O contrato {contrato.numero or contrato.pk} não está habilitado para gerar notas.'})
        if contrato.empresa_id != contrato.cliente.empresa_id:
            raise ValidationError({'contratos': 'O contrato e o cliente devem pertencer à mesma empresa.'})
        existing = list(Nota.objects.filter(contrato=contrato, competencia=competencia, exercicio=exercicio))
        if existing:
            if any(n.empresa_id != contrato.empresa_id for n in existing):
                raise NotaConflict('Existem notas com empresa inconsistente vinculadas ao contrato.')
            if len(existing) != 1 or existing[0].decimo_terceiro != decimo_terceiro:
                raise NotaConflict('Já existem notas nesta competência ou uma configuração diferente de décimo terceiro.')
            result.append((existing[0], False))
            continue
        conf = Ambiente.objects.filter(empresa_id=contrato.empresa_id).first()
        if conf is None or conf.aliquota_iss is None:
            raise ValidationError({'ambiente': 'Configure o ambiente e a alíquota fiscal desta empresa.'})
        if contrato.valor_bruto is None or not contrato.objeto:
            raise ValidationError({'contratos': 'Complete o valor bruto e o objeto do contrato.'})
        city = contrato.empresa.cidade if contrato.prestacao_municipio else contrato.cliente.cidade
        uf = city.uf if city else None
        if city is None or uf is None:
            raise ValidationError({'contratos': 'Informe o município da prestação de serviço.'})
        bruto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0')).run_validation(contrato.valor_bruto * (2 if decimo_terceiro else 1))
        aliquota = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100')).run_validation(Decimal(str(conf.aliquota_iss)).quantize(Decimal('0.01')))
        months = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']
        text = contrato.objeto.replace('MMMM', months[competencia - 1]).replace('YYYY', str(exercicio))
        if decimo_terceiro:
            text += ' E REFERENTE AO 13 SALÁRIO.'
        nota = Nota(empresa_id=contrato.empresa_id, contrato=contrato, competencia=competencia, exercicio=exercicio,
                    dt_data_emissao=timezone.now(), dt_data_vencimento=timezone.now() + timedelta(days=30),
                    valor_bruto=bruto, valor_liquido=bruto, imposto=(bruto * aliquota / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    aliq_imposto=aliquota, texto_nota=text, cidade=city, uf=uf, decimo_terceiro=decimo_terceiro,
                    coigo_servico=conf.coigo_servico, codigo_cnae=conf.codigo_cnae,
                    codigo_tributacao_municipio=conf.codigo_tributacao_municipio, descr_tributacao_municipio=conf.descr_tributacao_municipio)
        nota.clean()
        nota.save()
        result.append((nota, True))
    return result


@transaction.atomic
def gerar_receita(nota_id, usuario_id):
    nota = Nota.objects.select_for_update().select_related('contrato__cliente').get(pk=nota_id)
    if nota.operacoes.filter(estado__in=['executando', 'incerta']).exists():
        raise NotaConflict('Concilie as operações pendentes antes de gerar financeiro.')
    if nota.cancelada_em or not nota.protocolo_recebimento or not nota.numero:
        raise NotaConflict('Somente notas autorizadas e não canceladas podem gerar receita.')
    existing = list(DocReceita.objects.filter(nota=nota))
    if existing:
        if len(existing) != 1 or existing[0].empresa_id != nota.empresa_id:
            raise NotaConflict('Há documentos financeiros inconsistentes vinculados à nota.')
        return existing[0], False
    if nota.empresa_id != nota.contrato.empresa_id or nota.empresa_id != nota.contrato.cliente.empresa_id:
        raise NotaConflict('Empresa, contrato e cliente inconsistentes.')
    if nota.valor_bruto is None or nota.valor_bruto < 0:
        raise ValidationError({'valor_bruto': 'Informe um valor bruto válido.'})
    due = nota.dt_data_vencimento or nota.dt_data_emissao
    return DocReceita.objects.create(empresa_id=nota.empresa_id, cliente=nota.contrato.cliente, nota=nota,
        numero=nota.numero, descricao=f'Referente a nota {nota.numero} - {nota.texto_nota or ""}',
        dt_vencimento=timezone.localtime(due).date() if timezone.is_aware(due) else due.date(),
        valor=nota.valor_bruto, valor_recebido=0, dt_registro=timezone.localdate(), user_registro_id=usuario_id, situacao='A'), True


def validate_fiscal_data(nota):
    cliente = nota.contrato.cliente
    if not cliente.cnpj or not validar_cnpj(cliente.cnpj):
        raise ValidationError({'cliente': 'Informe um CNPJ válido para o cliente.'})
    if not all((cliente.instituicao, cliente.endereco, cliente.numero, cliente.bairro, cliente.cep,
                cliente.cidade_id, cliente.uf_id, nota.cidade_id, nota.uf_id, nota.texto_nota)):
        raise ValidationError({'cliente': 'Complete o endereço, município, UF e a descrição dos serviços.'})
    if cliente.cidade and cliente.cidade.uf_id != cliente.uf_id:
        raise ValidationError({'cliente': 'O município do cliente deve pertencer à UF cadastrada.'})
    if any(getattr(nota, field) is None for field in ('imposto', 'aliq_imposto', 'valor_liquido')):
        raise ValidationError({'valores': 'Complete ISS, alíquota e valor líquido antes de emitir.'})
    if not nota.valor_bruto or nota.valor_bruto < 0 or not nota.coigo_servico:
        raise ValidationError({'valor_bruto': 'Informe valor positivo e classificação fiscal para emitir.'})


def key_uuid(value):
    try:
        return uuid.UUID(str(value)) if value else uuid.uuid4()
    except (ValueError, TypeError):
        raise ValidationError({'idempotencia': 'Informe uma chave UUID válida.'})


def execute_operation(nota_id, usuario, acao, key=None, justificativa=''):
    key = key_uuid(key)
    gateway = get_gateway() if acao not in ('email', 'email_cliente') else None
    # Preflight não reserva sequências nem registra uma operação que não pode ser iniciada.
    initial = Nota.objects.select_related('contrato__cliente__cidade', 'contrato__cliente__uf', 'cidade', 'uf').get(pk=nota_id)
    existing = OperacaoFiscal.objects.filter(nota=initial, acao=acao, chave=key).first()
    if existing:
        return existing
    if gateway:
        try:
            gateway.check(initial)
        except FiscalConfigurationError as exc:
            raise IntegracaoIndisponivel(str(exc))
    else:
        from .mailing import check_email
        check_email(initial)
    with transaction.atomic():
        nota = Nota.objects.select_for_update().select_related('contrato__cliente').get(pk=nota_id)
        # Outra requisição pode ter reservado a mesma chave durante o preflight.
        existing = OperacaoFiscal.objects.filter(nota=nota, acao=acao, chave=key).first()
        if existing:
            return existing
        if gateway:
            # Coordena a reserva da operação com alterações de credenciais/ambiente.
            Ambiente.objects.select_for_update().get(empresa_id=nota.empresa_id)
            try:
                gateway.check(nota)
            except FiscalConfigurationError as exc:
                raise IntegracaoIndisponivel(str(exc))
        if acao in ('emitir', 'cancelar', 'email', 'email_cliente') and nota.operacoes.filter(estado__in=['executando', 'incerta']).exists():
            raise NotaConflict('Há uma operação pendente ou de resultado incerto. Consulte a nota antes de repetir.')
        if acao == 'emitir':
            if (nota.numero_rps is not None or nota.numero_lote is not None) and not nota.operacoes.filter(acao='emitir').exists():
                raise NotaConflict('Há RPS/lote legado sem resultado confirmado. Consulte a nota antes de qualquer emissão.')
            if nota.numero:
                raise NotaConflict('A nota possui número informado. Consulte seu resultado antes de emitir.')
            if nota.cancelada_em or nota.protocolo_envio or nota.protocolo_recebimento or nota.ja_enviou_NFSE:
                raise NotaConflict('Esta nota já foi transmitida ou cancelada. Consulte seu resultado; não a reenvie.')
            validate_fiscal_data(nota)
            conf = Ambiente.objects.select_for_update().get(empresa_id=nota.empresa_id)
            if nota.numero_lote is None or nota.numero_rps is None:
                try:
                    history = Nota.objects.filter(empresa_id=nota.empresa_id).aggregate(lote=Max('numero_lote'), rps=Max('numero_rps'))
                    batch = max(int(conf.numero_lote or 0), history['lote'] or 0) + 1
                    rps = max(int(conf.numero_rps or 0), history['rps'] or 0) + 1
                except ValueError:
                    raise ValidationError({'ambiente': 'Corrija os contadores de lote e RPS.'})
                if batch < 1 or rps < 1 or max(batch, rps) > 2147483647:
                    raise ValidationError({'ambiente': 'Os contadores de lote e RPS ultrapassam o limite suportado.'})
                conf.numero_lote, conf.numero_rps = str(batch), str(rps)
                conf.save(update_fields=['numero_lote', 'numero_rps'])
                nota.numero_lote, nota.numero_rps = batch, rps
                nota.save(update_fields=['numero_lote', 'numero_rps'])
        if acao == 'cancelar':
            if nota.cancelada_em or not nota.protocolo_recebimento or not nota.numero:
                raise NotaConflict('Somente notas autorizadas e não canceladas podem ser canceladas.')
            if not justificativa.strip():
                raise ValidationError({'justificativa': 'Registre a justificativa do cancelamento.'})
            # Cancelamento fiscal não estorna recebimentos nem exclui documentos financeiros.
            if nota.docreceitas.exists() or nota.dt_data_pagamento:
                raise NotaConflict('Concilie o financeiro antes de solicitar o cancelamento fiscal.')
        if acao == 'consultar_lote' and not nota.protocolo_envio:
            raise ValidationError({'protocolo_envio': 'Esta nota não possui protocolo de lote.'})
        if acao == 'consultar' and not nota.protocolo_envio and not nota.numero and not nota.numero_rps:
            raise ValidationError({'numero': 'Informe o número autorizado, RPS ou um protocolo para consultar.'})
        op = OperacaoFiscal.objects.create(nota=nota, usuario=usuario, acao=acao, chave=key,
                                           resultado={'justificativa': justificativa} if justificativa else {})
    try:
        nota = Nota.objects.select_related('contrato__cliente__cidade', 'contrato__cliente__uf', 'cidade', 'uf').get(pk=nota_id)
        if gateway:
            response = parse_response(gateway.execute(nota, acao), nota, acao)
        else:
            from .mailing import send_note_email
            response = send_note_email(nota, client_list=acao == 'email_cliente')
    except Exception:
        with transaction.atomic():
            locked = OperacaoFiscal.objects.select_for_update().get(pk=op.pk)
            locked.estado = 'incerta' if acao in ('emitir', 'cancelar', 'email', 'email_cliente') else 'falha'
            locked.resultado = {**locked.resultado, 'detail': 'Não foi possível confirmar o resultado externo. Nenhum reenvio automático foi realizado.'}
            locked.save()
        return locked
    try:
        with transaction.atomic():
            nota = Nota.objects.select_for_update().get(pk=nota_id)
            op = OperacaoFiscal.objects.select_for_update().get(pk=op.pk)
            op.estado = 'falha' if response.get('rejeitada') else 'concluida'
            op.resultado = {**op.resultado, **response}
            if acao == 'cancelar' and not response.get('cancelada') and not response.get('rejeitada'):
                op.estado = 'incerta'
                op.resultado['detail'] = 'O provedor não confirmou o cancelamento. Concilie antes de repetir.'
            if response.get('protocolo') and acao != 'cancelar':
                nota.protocolo_envio = response['protocolo']
                nota.ja_enviou_NFSE = True
                nota.dt_data_envio_sefaz = parse_provider_datetime(response.get('data_recebimento')) or timezone.now()
            if response.get('autorizada'):
                nota.numero = response['numero']
                nota.protocolo_recebimento = response['codigo_verificacao']
                nota.ja_enviou_NFSE = True
                nota.dt_data_autorizacao = parse_provider_datetime(response.get('data_emissao')) or timezone.now()
                nota.operacoes.filter(acao='emitir', estado__in=['executando', 'incerta']).exclude(pk=op.pk).update(
                    estado='concluida', resultado={'conciliada_por': str(op.pk), 'detail': 'Autorização confirmada em consulta.'}, atualizada_em=timezone.now())
            if response.get('cancelada'):
                nota.cancelada_em = parse_provider_datetime(response.get('data_cancelamento')) or timezone.now()
                nota.dt_data_envio_can = timezone.now()
                nota.prot_envio_can = 'CONFIRMADO'
                nota.operacoes.filter(acao='cancelar', estado__in=['executando', 'incerta']).exclude(pk=op.pk).update(
                    estado='concluida', resultado={'conciliada_por': str(op.pk), 'detail': 'Cancelamento confirmado em consulta.'}, atualizada_em=timezone.now())
            if response.get('email_enviado'):
                nota.ja_enviou = True
                nota.dt_data_envio = timezone.now()
            nota.save()
            op.save()
    except Exception:
        # A chamada externa pode ter sido aceita mesmo que a persistência local falhe.
        OperacaoFiscal.objects.filter(pk=op.pk).update(estado='incerta', resultado={'detail': 'Resultado externo recebido, mas a confirmação local falhou. Consulte a nota.'}, atualizada_em=timezone.now())
        return OperacaoFiscal.objects.get(pk=op.pk)
    return op
