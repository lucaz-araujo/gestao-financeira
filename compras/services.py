from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from conta.services import ContaConflict
from .models import Solicitacao, OrcamentoItens
from .serializers import total_linha


def bloquear_solicitacao(pk):
    return Solicitacao.objects.select_for_update().get(pk=pk)


def estado_editavel(obj, states):
    if obj.status not in states:
        raise ContaConflict('A solicitação está bloqueada nesta etapa. Revise seu status antes de alterar.')


@transaction.atomic
def mudar_estado(obj, target, usuario):
    obj = bloquear_solicitacao(obj.pk)
    transitions = {'AB': {'PE','CA'}, 'PE': {'AU','CA'}, 'AU': {'CA'}, 'FI': set(), 'CA': set()}
    if target not in transitions.get(obj.status,set()):
        raise ContaConflict('Transição de status não permitida.')
    if target == 'AU':
        if not usuario.has_perm('compras.autorizar_solicitacao'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Sem permissão para autorizar compras.')
        conferir_cotacoes(obj)
        obj.user_autorizacao, obj.dt_autorizacao = usuario, timezone.localdate()
    obj.status = target; obj.save()
    return obj


def conferir_cotacoes(obj):
    requested = list(obj.solicitacaoitem_set.select_related('item__unidade'))
    if not requested: raise ContaConflict('A solicitação não possui itens.')
    winners = []
    for row in requested:
        if row.item.empresa_id != obj.empresa_id or row.item.unidade.empresa_id != obj.empresa_id or row.quantidade <= 0:
            raise ContaConflict('Há itens antigos inconsistentes. Concilie a solicitação.')
        quotes = list(OrcamentoItens.objects.filter(orcamento__solicitacao=obj,orcamento__empresa_id=obj.empresa_id,
            orcamento__fornecedor__empresa_id=obj.empresa_id,item=row.item,quantidade=row.quantidade,valor__gte=0).select_related('orcamento').order_by('valor','orcamento__dt_orcamento','pk'))
        if not quotes: raise ContaConflict('Todos os itens precisam de cotação da quantidade solicitada antes da autorização/finalização.')
        winner = quotes[0]
        if winner.valor_total != total_linha(winner.quantidade,winner.valor):
            raise ContaConflict('A cotação possui total inconsistente. Corrija antes de autorizar.')
        winners.append((row,winner))
    if sum(total_linha(row.quantidade,winner.valor) for row,winner in winners)>Decimal('9999999.999'):
        raise ContaConflict('O total selecionado ultrapassa o limite do cadastro.')
    return winners


@transaction.atomic
def finalizar(obj):
    obj = bloquear_solicitacao(obj.pk)
    if obj.status == 'FI': return obj
    estado_editavel(obj,{'AU'})
    winners = conferir_cotacoes(obj)
    OrcamentoItens.objects.filter(orcamento__solicitacao=obj).update(menor_preco=False)
    for row,winner in winners:
        winner.menor_preco=True;winner.save(update_fields=['menor_preco'])
        row.orcamento=winner;row.valor=winner.valor;row.valor_total=total_linha(row.quantidade,row.valor)
        row.save(update_fields=['orcamento','valor','valor_total'])
    obj.atuTotal();obj.status='FI';obj.save(update_fields=['status'])
    return obj
