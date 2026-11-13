"""Aplica a correção local após os testes. Não imprime URLs nem credenciais.

Uso: .venv/bin/python scripts/configure_postgres.py --database gestao_financeira_teste --apply
Cria backup completo, aplica migrations, corrige sequências e configura login de runtime.
"""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ['DJANGO_SETTINGS_MODULE'] = 'layCliente.settings'
os.environ['DATABASE_USE_ADMIN'] = '1'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--apply', action='store_true', required=True)
    args = parser.parse_args()
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection, transaction
    from environ import Env
    from psycopg import sql
    import psycopg

    cfg = settings.DATABASES['default']
    if cfg['NAME'] != args.database or cfg['ENGINE'] != 'django.db.backends.postgresql':
        raise RuntimeError('O banco solicitado não corresponde à configuração administrativa.')
    env_path = ROOT / '.env'
    env_text = env_path.read_text()
    role = 'gestao_financeira_app'
    runtime_cfg = Env.db_url_config(os.environ['DATABASE_URL'])
    backup_dir = ROOT / '.backups'
    backup_dir.mkdir(mode=0o700, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    backup = backup_dir / (args.database + '_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.dump')
    backup.touch(mode=0o600, exist_ok=False)
    dump_env = {**os.environ, 'PGHOST': cfg.get('HOST') or 'localhost', 'PGPORT': str(cfg.get('PORT') or 5432),
                'PGUSER': cfg['USER'], 'PGPASSWORD': cfg['PASSWORD'], 'PGDATABASE': cfg['NAME']}
    subprocess.run(['pg_dump', '--format=custom', '--file', str(backup)], env=dump_env, check=True)
    subprocess.run(['pg_restore', '--list', str(backup)], stdout=subprocess.DEVNULL, check=True)
    print('Backup criado e catálogo verificado:', backup.relative_to(ROOT))
    call_command('migrate', interactive=False)
    call_command('repair_pg_sequences', apply=True)

    with transaction.atomic(), connection.cursor() as c:
        c.execute('SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=%s', [role])
        existing = c.fetchone()
        if existing:
            if runtime_cfg['USER'] != role or any(existing):
                raise RuntimeError('O nome do login já existe sem corresponder à configuração restrita esperada.')
            password = runtime_cfg['PASSWORD']
        else:
            password = secrets.token_urlsafe(40)
            c.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(
                sql.Identifier(role), sql.Literal(password)))
        c.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(cfg['NAME']), sql.Identifier(role)))
        c.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        c.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
        c.execute(sql.SQL('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}').format(sql.Identifier(role)))
        c.execute(sql.SQL('REVOKE INSERT, UPDATE, DELETE ON public.django_migrations FROM {}').format(sql.Identifier(role)))
        c.execute(sql.SQL('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(role)))
        c.execute(sql.SQL('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {}').format(sql.Identifier(role)))
        owner = sql.Identifier(cfg['USER'])
        c.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}').format(owner, sql.Identifier(role)))
        c.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}').format(owner, sql.Identifier(role)))
        c.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {}').format(owner, sql.Identifier(role)))

    with psycopg.connect(host=cfg.get('HOST') or 'localhost', port=cfg.get('PORT') or 5432,
                         dbname=cfg['NAME'], user=role, password=password) as runtime:
        with runtime.cursor() as c:
            c.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,has_schema_privilege(current_user,'public','CREATE') FROM pg_roles WHERE rolname=current_user")
            if any(c.fetchone()):
                raise RuntimeError('O usuário de runtime possui privilégios administrativos inesperados.')
            c.execute('SELECT COUNT(*) FROM clientes_cliente')
            print('Leitura com login restrito:', c.fetchone()[0], 'clientes')
            c.execute('INSERT INTO clientes_uf (sigla,descricao) VALUES (%s,%s) RETURNING id', ['TEST', 'Validação transacional'])
            pk = c.fetchone()[0]
            c.execute('UPDATE clientes_uf SET descricao=%s WHERE id=%s', ['Atualizado', pk])
            c.execute('DELETE FROM clientes_uf WHERE id=%s', [pk])
        runtime.rollback()  # Nenhum registro de teste permanece no banco atual.
    host = cfg.get('HOST') or 'localhost'
    if ':' in host:
        host = '[' + host + ']'
    url = f"postgresql://{role}:{quote(password, safe='')}@{host}:{cfg.get('PORT') or 5432}/{quote(cfg['NAME'], safe='')}"
    admin_url = os.environ.get('DATABASE_ADMIN_URL', os.environ['DATABASE_URL'])
    lines = [line for line in env_text.splitlines() if not line.startswith(('DATABASE_URL=', 'DATABASE_ADMIN_URL=', 'DATABASE_USE_ADMIN='))]
    lines += ['DATABASE_URL=' + url, 'DATABASE_ADMIN_URL=' + admin_url]
    temp = env_path.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write('\n'.join(lines) + '\n')
    os.chmod(temp, 0o600)
    os.replace(temp, env_path)
    print('Configuração atualizada: runtime restrito, migrations com DATABASE_USE_ADMIN=1.')
    call_command('repair_pg_sequences')
    call_command('check', databases=['default'])


if __name__ == '__main__':
    main()
