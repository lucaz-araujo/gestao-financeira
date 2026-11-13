"""Perfil de publicação; ativar com DJANGO_SETTINGS_MODULE=layCliente.production."""
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured
from .settings import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])
_origin = urlsplit(PUBLIC_APP_URL)
if not ALLOWED_HOSTS or any('*' in host or host.startswith('.') for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('Defina ALLOWED_HOSTS com os domínios explícitos de produção.')
if _origin.scheme != 'https' or not _origin.hostname or _origin.username or _origin.password or _origin.path not in ('', '/') or _origin.query or _origin.fragment or _origin.hostname not in ALLOWED_HOSTS or _origin.hostname.endswith('.invalid'):
    raise ImproperlyConfigured('PUBLIC_APP_URL deve ser uma origem HTTPS em ALLOWED_HOSTS.')
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith(('django-insecure-', 'SUBSTITUIR_')):
    raise ImproperlyConfigured('Configure uma SECRET_KEY forte e exclusiva para produção.')
if not API_SECRET_KEY or API_SECRET_KEY.startswith('CHAVE_ATUAL_'):
    raise ImproperlyConfigured('Configure o segredo real das integrações antes de publicar.')
if env.bool('DATABASE_USE_ADMIN', default=False):
    raise ImproperlyConfigured('O servidor de produção deve usar o login restrito do banco.')

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CLIENTES_AUTH_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600  # Inicialmente uma hora; ampliar após validar o HTTPS.
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
CSRF_TRUSTED_ORIGINS = [PUBLIC_APP_URL]
# Ativar somente atrás de proxy que sobrescreve o cabeçalho e isola o backend.
TRUST_PROXY_HTTPS = env.bool('TRUST_PROXY_HTTPS', default=False)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if TRUST_PROXY_HTTPS else None

_cache_url = env('CACHE_URL', default='')
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': _cache_url}} if _cache_url else {
    'default': {'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache', 'LOCATION': os.path.join(BASE_DIR, '.private', 'cache')}
}
