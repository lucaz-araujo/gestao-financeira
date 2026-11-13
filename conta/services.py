"""Movimentações locais atômicas; não realiza transferências em instituições bancárias."""
from decimal import Decimal
from django.db import transaction
from django.db.models import Max
from rest_framework.exceptions import APIException
from financeiro.models import FechamentoCaixa, RecReceita, PagDespesa
from .models import Conta, Movimento


class ContaConflict(APIException):
    status_code = 409
    default_code = 'conflict'
    default_detail = 'A operação conflita com o histórico financeiro.'


def bloquear_contas(ids, empresa_id):
    ids = set(ids)
    accounts = list(Conta.objects.select_for_update().filter(pk__in=ids, empresa_id=empresa_id).order_by('pk'))
    if len(accounts) != len(ids):
        raise ContaConflict('Há contas inexistentes ou de outra empresa nesta operação.')
    return accounts


def periodo_aberto(contas, dia):
    latest = FechamentoCaixa.objects.filter(conta_id__in=contas).aggregate(ultimo=Max('data'))['ultimo']
    if latest and dia <= latest:
        raise ContaConflict('O período está fechado em pelo menos uma das contas. Reabra o caixa antes de movimentar.')


def manual(mov):
    if mov.receita_id or mov.despesa_id or mov.transferencia_id or mov.tipo_documento == 'TRA':
        raise ContaConflict('Movimento vinculado: altere ou exclua pela operação de origem.')


def validar_par(transfer):
    legs = list(transfer.transferencia.select_for_update().order_by('pk'))
    if not transfer.par_consistente(legs):
        raise ContaConflict('A transferência possui movimentos ausentes, duplicados ou inconsistentes. Concilie antes de alterar.')
    return legs


@transaction.atomic
def gravar_transferencia(serializer, usuario, empresa_id):
    old = serializer.instance
    values = serializer.validated_data
    origin = values.get('conta_origem', old.conta_origem if old else None)
    destination = values.get('conta_destino', old.conta_destino if old else None)
    day = values.get('dt_movimento', old.dt_movimento if old else None)
    ids = {origin.pk, destination.pk}
    if old:
        ids.update([old.conta_origem_id, old.conta_destino_id])
    bloquear_contas(ids, empresa_id)
    if old:
        periodo_aberto([old.conta_origem_id, old.conta_destino_id], old.dt_movimento)
        legs = validar_par(old)
    else:
        legs = []
    periodo_aberto([origin.pk, destination.pk], day)
    transfer = serializer.save(empresa_id=empresa_id, usuario=usuario)
    for direction, account in [('D', origin), ('C', destination)]:
        leg = next((m for m in legs if m.tipo_movimento == direction), Movimento(transferencia=transfer))
        leg.empresa_id, leg.conta = empresa_id, account
        leg.tipo_documento, leg.tipo_movimento = 'TRA', direction
        leg.nr_documento, leg.dt_movimento = transfer.nr_documento, transfer.dt_movimento
        leg.valor, leg.historico, leg.usuario = transfer.valor, transfer.historico, usuario
        leg.clean()
        leg.save()
    return transfer


@transaction.atomic
def sincronizar_pagamento(obj, tipo):
    if tipo not in ('c', 'd'):
        raise ContaConflict('Tipo de pagamento inválido.')
    source = (RecReceita if tipo == 'c' else PagDespesa).objects.select_for_update().get(pk=obj.pk)
    document = source.receita if tipo == 'c' else source.despesa
    field = 'receita' if tipo == 'c' else 'despesa'
    existing = list(Movimento.objects.filter(**{field: source}).order_by('pk'))
    if len(existing) > 1:
        raise ContaConflict('Há movimentos duplicados para este pagamento. Concilie antes de continuar.')
    if not source.conta_id or source.valor <= 0:
        raise ContaConflict('Informe conta e valor positivo para o pagamento.')
    ids = [source.conta_id] + [m.conta_id for m in existing]
    bloquear_contas(ids, document.empresa_id)
    for m in existing:
        if m.empresa_id != document.empresa_id:
            raise ContaConflict('O vínculo financeiro possui empresa inconsistente.')
        periodo_aberto([m.conta_id], m.dt_movimento)
    periodo_aberto([source.conta_id], source.dt_pagamento)
    movement = existing[0] if existing else Movimento()
    movement.empresa_id, movement.conta_id = document.empresa_id, source.conta_id
    movement.tipo_movimento = 'C' if tipo == 'c' else 'D'
    cheque = tipo == 'd' and source.forma_pagamento == 'C'
    movement.tipo_documento = 'CHE' if cheque else 'OUT'
    movement.nr_documento = str(source.numero_cheque or '') if cheque else str(document.numero if tipo == 'c' else document.pk)
    movement.dt_movimento, movement.valor = source.dt_pagamento, source.valor
    movement.usuario = source.user_registro
    movement.historico = (document.descricao or '')[:560]
    setattr(movement, field, source)
    movement.clean()
    movement.save()
    return movement
