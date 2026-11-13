"""Permissões delegáveis pelo cadastro operacional, sem privilégios administrativos."""
from django.contrib.auth.models import Permission

BUSINESS_APPS = (
    'agenda', 'chaves', 'clientes', 'compras', 'configambiente', 'conta',
    'contabil', 'contratos', 'empresa', 'financeiro', 'notas', 'produtos',
    'recadclientes', 'servicos',
)


def permissoes_delegaveis(user):
    allowed = user.get_all_permissions()
    ids = []
    for permission in Permission.objects.select_related('content_type').filter(content_type__app_label__in=BUSINESS_APPS):
        code = f'{permission.content_type.app_label}.{permission.codename}'
        if code in allowed and permission.codename.startswith(('view_', 'add_', 'change_', 'delete_')) and code != 'empresa.add_empresa':
            ids.append(permission.pk)
    return Permission.objects.filter(pk__in=ids).select_related('content_type').order_by('content_type__app_label', 'codename')
