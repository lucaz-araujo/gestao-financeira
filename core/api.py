"""Regras de contexto compartilhadas pelas APIs dos apps migrados."""
from rest_framework.exceptions import PermissionDenied, ValidationError


def empresa_da_requisicao(request):
    value = request.headers.get('X-Empresa-ID')
    if value is None:
        value = request.query_params.get('empresa')
    if value is None:
        value = request.session.get('empresa')
    try:
        empresa_id = int(value)
        if empresa_id < 1:
            raise ValueError
    except (TypeError, ValueError):
        raise ValidationError({'empresa': 'Informe uma empresa válida.'})
    if not request.user.empresas.filter(pk=empresa_id).exists():
        raise PermissionDenied('Empresa fora do seu escopo de acesso.')
    return empresa_id
