"""Diagnóstico operacional sem emissão fiscal, envio de mensagens ou alteração de dados."""
from urllib.parse import urlsplit
from django.conf import settings
from django.db.models import Count, F
from clientes.models import Cliente, Liberacao
from configambiente.models import Ambiente
from notas.gateway import fiscal_status
from usuario.services import recovery_available


def deployment_status():
    origin = urlsplit(settings.PUBLIC_APP_URL)
    return {
        'debug_desativado': not settings.DEBUG,
        'hosts_restritos': bool(settings.ALLOWED_HOSTS) and all('*' not in host and not host.startswith('.') for host in settings.ALLOWED_HOSTS),
        'origem_https': origin.scheme == 'https' and bool(origin.hostname) and origin.hostname in settings.ALLOWED_HOSTS,
        'redirecionamento_https': settings.SECURE_SSL_REDIRECT,
        'cookies_seguros': all((settings.SESSION_COOKIE_SECURE, settings.CSRF_COOKIE_SECURE, settings.CLIENTES_AUTH_COOKIE_SECURE)),
        'hsts_ativo': settings.SECURE_HSTS_SECONDS > 0,
        'email_recuperacao_configurado': recovery_available(),
        'smtp_remetente_configurado': bool(settings.DEFAULT_FROM_EMAIL and settings.EMAIL_HOST),
        'throttle_compartilhado': settings.CACHES['default']['BACKEND'] != 'django.core.cache.backends.locmem.LocMemCache',
    }


def legacy_audit():
    identities = list(Cliente.objects.exclude(codigolayout__isnull=True).exclude(codigoentidade__isnull=True)
                      .exclude(codigolayout='').exclude(codigoentidade='').order_by()
                      .values('codigolayout', 'codigoentidade').annotate(total=Count('pk')).filter(total__gt=1))
    for group in identities:
        group['clientes_ids'] = list(Cliente.objects.filter(codigolayout=group['codigolayout'], codigoentidade=group['codigoentidade']).order_by('pk').values_list('pk', flat=True))
    periods = list(Liberacao.objects.filter(cliente__isnull=False).order_by().values('cliente_id', 'competencia', 'exercicio').annotate(total=Count('pk')).filter(total__gt=1))
    mismatched = list(Liberacao.objects.filter(cliente__isnull=False).exclude(codigo=F('cliente__codigoentidade'), codigo_layout=F('cliente__codigolayout')).order_by('pk').values_list('pk', flat=True))
    return {
        'identidades_ambiguas': identities,
        'periodos_com_multiplas_liberacoes': periods,
        'liberacoes_com_codigos_diferentes_do_cadastro_atual_ids': mismatched,
        'observacao': 'Diferenças históricas não comprovam erro. Não alterar liberações/chaves sem conciliação administrativa.',
    }


def fiscal_audit():
    results = []
    for company_id in Ambiente.objects.order_by('empresa_id').values_list('empresa_id', flat=True):
        try:
            status = fiscal_status(company_id)
        except Exception:
            status = {'disponivel': False, 'pendencias': ['Não foi possível ler a configuração fiscal. Revise o armazenamento e as chaves.']}
        results.append({'empresa_id': company_id, **status})
    return results
