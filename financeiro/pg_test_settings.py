"""Testes com migrations reais em banco PostgreSQL separado e descartável."""
from layCliente.settings import *  # noqa: F403
import os

if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise RuntimeError('Os testes de integração exigem PostgreSQL.')
DATABASES['default']['TEST'] = {'NAME': os.environ.get('PG_INTEGRATION_TEST_DB', 'test_gestao_integracao_pg')}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
SECRET_KEY = 'isolated-postgresql-tests-only-1234567890123456789'

# Servidores de navegador de teste usam HTTP e dados isolados.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
