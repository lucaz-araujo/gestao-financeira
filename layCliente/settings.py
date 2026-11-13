import os
from datetime import timedelta
from environ import Env
from django.contrib.messages import constants as messages

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

env = Env(DEBUG=(bool, False))
env.read_env(os.environ.get('DJANGO_ENV_FILE', os.path.join(BASE_DIR, '.env')))

SECRET_KEY = env('SECRET_KEY', default='django-insecure-local-migration-key')
SECRET_KEY_FALLBACKS = env.list('SECRET_KEY_FALLBACKS', default=[])
DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1', '[::1]'])

# Application definition
INSTALLED_APPS = [
    'core',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'rest_framework',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # 'django_filters',
    'usuario',
    'produtos',
    'dashboard',
    'recadclientes',
    'clientes',
    'contratos',
    'notas',
    'conta',
    'configambiente',
    'pynfe',
    'compras',
    'contabil',
    'financeiro',
    'agenda',
    'auditlog',
    'chaves',
    'servicos',
    'empresa',
]

MIDDLEWARE = [
    'core.middleware.TrustedProxyMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
]

ROOT_URLCONF = 'layCliente.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR,'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'layCliente.wsgi.application'


# A aplicação usa um login restrito; migrations podem selecionar a URL administrativa.
# As duas URLs devem apontar para o mesmo banco; a opção administrativa é explícita.
_database_url = env('DATABASE_URL')
if env.bool('DATABASE_USE_ADMIN', default=False):
    _database_url = env('DATABASE_ADMIN_URL', default=_database_url)
DATABASES = {'default': Env.db_url_config(_database_url)}

# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Fortaleza'

USE_I18N = True

USE_TZ = True

# Keep the legacy integer primary keys unchanged during the database migration.
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

USE_THOUSAND_SEPARATOR = True

THOUSAND_SEPARATOR = '.'

NUMBER_GROUPING = 3

DECIMAL_SEPARATOR = ','


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, "static"),
)

DATE_FORMAT = 'd/m/Y'

DATE_INPUT_FORMATS = (
    '%d/%m/%Y',
)

AUTH_USER_MODEL = 'usuario.Usuario'

LOGIN_URL = "/usuario/login/"
LOGOUT_URL = "/usuario/logout/"


LAYOUT_CNPJ='73807711000146'
LAYOUT_INSCRICAO_MUNICIPAL='102040880'


HOST_XSD = 'http://127.0.0.1:8000'

API_SECRET_KEY = env('API_SECRET_KEY')
API_INTEGRATION_USER_ID = env.int('API_INTEGRATION_USER_ID', default=11)
API_LEGACY_RATE = env('API_LEGACY_RATE', default='600/min')

MESSAGE_TAGS = {
    messages.DEBUG: 'info',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'error',
}

DATA_UPLOAD_MAX_NUMBER_FIELDS = 10240


REST_FRAMEWORK = {
    'NUM_PROXIES': 0,  # Ignora X-Forwarded-For não confiável nos throttles.
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'CHECK_REVOKE_TOKEN': True,
    'TOKEN_REFRESH_SERIALIZER': 'usuario.tokens.PasswordAwareTokenRefreshSerializer',
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}
CLIENTES_AUTH_COOKIE_SECURE = env.bool('CLIENTES_AUTH_COOKIE_SECURE', default=not DEBUG)


# Envio fiscal/e-mail é configurado por ambiente; nenhuma credencial fica no código.
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='financeiro@layoutsistemas.com.br')
PUBLIC_APP_URL = env('PUBLIC_APP_URL', default='').rstrip('/')
NOTAS_PUBLIC_LINK_MAX_AGE = 7 * 24 * 60 * 60

USUARIO_PASSWORD_RESET_TIMEOUT = 30 * 60
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=not DEBUG)

# Opções locais explícitas; o perfil production impõe os valores de publicação.
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0)
PRIVATE_CERTIFICATE_ROOT = env('PRIVATE_CERTIFICATE_ROOT', default=os.path.join(BASE_DIR, '.private', 'certificados'))

TRUST_PROXY_HTTPS = False
TRUSTED_PROXY_IPS = env.list('TRUSTED_PROXY_IPS', default=['127.0.0.1', '::1'])
