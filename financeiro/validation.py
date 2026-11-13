"""Invariantes também aplicadas pela API; o navegador não é uma fronteira de confiança."""
from django.core.exceptions import ValidationError


def documento_limpo(obj):
    errors = {}
    if obj.valor is not None and obj.valor <= 0:
        errors['valor'] = 'Informe um valor positivo.'
    for field in ('cliente', 'fornecedor', 'centro_custo'):
        if getattr(obj, field + '_id', None) and getattr(obj, field).empresa_id != obj.empresa_id:
            errors[field] = 'O vínculo deve pertencer à empresa selecionada.'
    if getattr(obj, 'tipo_despesa_id', None):
        plan = obj.tipo_despesa.conta
        if plan and plan.empresa_id != obj.empresa_id:
            errors['tipo_despesa'] = 'O plano do tipo de despesa pertence a outra empresa.'
    if getattr(obj, 'nota_id', None):
        note = obj.nota
        if note.empresa_id != obj.empresa_id or note.contrato.cliente_id != obj.cliente_id:
            errors['nota'] = 'A nota deve pertencer à empresa e ao cliente selecionados.'
        elif note.cancelada_em:
            errors['nota'] = 'A nota está cancelada.'
    if errors:
        raise ValidationError(errors)


def baixa_limpa(obj):
    errors = {}
    document = getattr(obj, 'receita', None) or getattr(obj, 'despesa', None)
    if not obj.conta_id or (document and obj.conta.empresa_id != document.empresa_id):
        errors['conta'] = 'Informe uma conta da empresa do documento.'
    if obj.valor is not None and obj.valor <= 0:
        errors['valor'] = 'Informe um valor positivo.'
    if getattr(obj, 'forma_pagamento', None) == 'C' and not (obj.numero_cheque or '').strip():
        errors['numero_cheque'] = 'Informe o número do cheque.'
    if errors:
        raise ValidationError(errors)
