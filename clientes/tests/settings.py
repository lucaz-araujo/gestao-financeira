"""Banco efêmero para testes de comportamento, sem acessar o PostgreSQL local.

Executar: .venv/bin/python manage.py test clientes.tests --settings=clientes.tests.settings
Não valida migrations PostgreSQL: cria o schema diretamente dos modelos atuais.
"""
from layCliente.settings import *  # noqa: F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
SECRET_KEY = 'test-only-clientes-key-not-for-deployment-1234567890'
# Todos os apps possuem dependências entre si; criar o schema sem o histórico legado.
MIGRATION_MODULES = {name.rsplit('.', 1)[-1]: None for name in INSTALLED_APPS}
