"""Fronteira transacional das operações financeiras específicas do PostgreSQL."""
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from conta.models import Conta
from .models import Analise

MONTHS = ('jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez')


def empresa_autorizada(usuario, empresa):
    try:
        empresa = int(empresa)
    except (TypeError, ValueError):
        raise PermissionDenied('Selecione uma empresa válida.')
    if not usuario.empresas.filter(pk=empresa).exists():
        raise PermissionDenied('Empresa não autorizada.')
    return empresa


def validar_periodo(inicio, fim):
    if not inicio or not fim or fim < inicio:
        raise ValidationError('Informe as datas inicial e final em ordem válida.')


@transaction.atomic
def fechar_caixa(usuario, empresa, conta_id, inicio, fim):
    empresa = empresa_autorizada(usuario, empresa)
    validar_periodo(inicio, fim)
    if (fim - inicio).days > 3660:
        raise ValidationError('O período não pode ultrapassar 3661 dias.')
    if not Conta.objects.filter(pk=conta_id, empresa_id=empresa).exists():
        raise PermissionDenied('Conta não pertence à empresa selecionada.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT public.fechamento(%s, %s, %s, %s)', [inicio, fim, conta_id, usuario.pk])
        return cursor.fetchone()[0]


def analise_financeira(usuario, empresa, inicio, fim):
    empresa = empresa_autorizada(usuario, empresa)
    validar_periodo(inicio, fim)
    rows = list(Analise.objects.raw('SELECT * FROM public.fn_analise(%s, %s, %s)', [inicio, fim, empresa]))
    totals = {month + 'v': Decimal('0') for month in MONTHS}
    for row in rows:
        sign = 1 if row.tipo_movimento == 'C' else -1
        for month in MONTHS:
            totals[month + 'v'] += sign * getattr(row, month + 'r')
    return rows, totals


# As rotinas abaixo somente registram baixas locais; não acionam bancos ou serviços fiscais.
def total_documento(documento):
    from django.db.models import Sum
    relation = documento.recebimento if hasattr(documento, 'recebimento') else documento.pagamentos
    return relation.aggregate(total=Sum('valor'))['total'] or Decimal('0')


def conferir_movimento(baixa, receita):
    from conta.models import Movimento
    from conta.services import ContaConflict
    field = 'receita' if receita else 'despesa'
    doc = getattr(baixa, field)
    moves = list(Movimento.objects.filter(**{field: baixa}))
    if len(moves) != 1:
        raise ContaConflict('A baixa possui movimentos ausentes ou duplicados. Concilie o histórico antes de alterar.')
    move = moves[0]
    if (move.empresa_id != doc.empresa_id or move.conta_id != baixa.conta_id or
        move.valor != baixa.valor or move.dt_movimento != baixa.dt_pagamento or
        move.tipo_movimento != ('C' if receita else 'D') or move.transferencia_id or
        (move.despesa_id if receita else move.receita_id)):
        raise ContaConflict('A baixa e seu movimento estão inconsistentes. Concilie antes de alterar.')
    return move


def atualizar_documento(documento):
    from django.utils import timezone
    from .models import DocReceita, RecReceita
    receipt = isinstance(documento, DocReceita)
    total = total_documento(documento)
    field = 'valor_recebido' if receipt else 'valor_pago'
    setattr(documento, field, total)
    documento.situacao = ('R' if receipt else 'P') if total >= documento.valor else 'A'
    documento.save(update_fields=[field, 'situacao'])
    if receipt:
        note = documento.nota
        docs = list(DocReceita.objects.filter(nota=note))
        settled = bool(docs) and all(total_documento(doc) >= doc.valor for doc in docs)
        last = RecReceita.objects.filter(receita__nota=note).order_by('-dt_pagamento', '-pk').first()
        note.dt_data_pagamento = last.dt_pagamento if settled and last else None
        note.save(update_fields=['dt_data_pagamento'])
        if settled and last:
            # O bloqueio da nota serializa as parcelas; libera somente na quitação integral.
            last.liberames()
        # Liberações manuais preexistentes nunca são removidas implicitamente pelo estorno.


def bloquear_documento(documento):
    from .models import DocReceita
    from notas.models import Nota
    from conta.services import ContaConflict
    if isinstance(documento, DocReceita):
        note = Nota.objects.select_for_update().get(pk=documento.nota_id)
        if note.cancelada_em or note.operacoes.filter(estado__in=['executando', 'incerta']).exists():
            raise ContaConflict('Concilie o estado fiscal da nota antes de alterar o financeiro.')
    return type(documento).objects.select_for_update().get(pk=documento.pk)


@transaction.atomic
def registrar_baixa(documento, values, usuario):
    import hashlib
    import json
    from django.db import IntegrityError
    from .models import DocReceita, RecReceita, PagDespesa, OperacaoBaixa
    from conta.services import ContaConflict, bloquear_contas, periodo_aberto, sincronizar_pagamento
    documento = bloquear_documento(documento)
    documento.clean()
    receipt = isinstance(documento, DocReceita)
    resource = 'recebimentos' if receipt else 'pagamentos'
    model = RecReceita if receipt else PagDespesa
    values = dict(values)
    key = values.pop('idempotencia')
    canonical = {k: str(v.pk if hasattr(v, 'pk') else v) for k, v in values.items()}
    digest = hashlib.sha256(json.dumps([resource, documento.pk, canonical], sort_keys=True).encode()).hexdigest()
    existing = OperacaoBaixa.objects.filter(pk=key).first()
    if existing:
        if existing.empresa_id != documento.empresa_id or existing.assinatura != digest:
            raise ContaConflict('A chave desta operação já foi usada com outros dados.')
        obj = model.objects.filter(pk=existing.registro).first()
        if not obj:
            raise ContaConflict('Esta operação já foi estornada. Use uma nova operação para registrar outra baixa.')
        return obj, False
    relation = documento.recebimento if receipt else documento.pagamentos
    for previous in relation.all():
        conferir_movimento(previous, receipt)
    remaining = documento.valor - total_documento(documento)
    if values['valor'] > remaining:
        raise ValidationError({'valor': 'O valor ultrapassa o saldo em aberto do documento.'})
    account = values['conta']
    bloquear_contas([account.pk], documento.empresa_id)
    periodo_aberto([account.pk], values['dt_pagamento'])
    obj = model(**values, **{'receita' if receipt else 'despesa': documento}, user_registro=usuario)
    obj.clean()
    obj.save()
    sincronizar_pagamento(obj, 'c' if receipt else 'd')
    atualizar_documento(documento)
    # A restrição da PK também protege requisições concorrentes para documentos distintos.
    try:
        with transaction.atomic():
            OperacaoBaixa.objects.create(chave=key, empresa_id=documento.empresa_id, usuario=usuario,
                assinatura=digest, recurso=resource, registro=obj.pk)
    except IntegrityError:
        raise ContaConflict('Esta chave já foi processada. Atualize a tela antes de repetir.')
    return obj, True


@transaction.atomic
def estornar_baixa(documento, registro):
    from .models import DocReceita
    from conta.services import bloquear_contas, periodo_aberto, ContaConflict
    documento = bloquear_documento(documento)
    receipt = isinstance(documento, DocReceita)
    relation = documento.recebimento if receipt else documento.pagamentos
    obj = relation.select_for_update().filter(pk=registro).first()
    if not obj:
        raise ContaConflict('Baixa inexistente ou já estornada.')
    move = conferir_movimento(obj, receipt)
    bloquear_contas([obj.conta_id], documento.empresa_id)
    periodo_aberto([obj.conta_id], obj.dt_pagamento)
    move.delete()
    obj.delete()
    atualizar_documento(documento)


@transaction.atomic
def reabrir_caixa(usuario, empresa, registro):
    from .models import FechamentoCaixa
    from conta.services import bloquear_contas, ContaConflict
    empresa_autorizada(usuario, empresa)
    obj = FechamentoCaixa.objects.get(pk=registro, empresa_id=empresa)
    bloquear_contas([obj.conta_id], empresa)
    obj = FechamentoCaixa.objects.select_for_update().get(pk=registro, empresa_id=empresa)
    if FechamentoCaixa.objects.filter(conta_id=obj.conta_id, data__gt=obj.data).exists():
        raise ContaConflict('Reabra primeiro o último fechamento desta conta.')
    obj.delete()
