"""Audita sequências e, com --apply, avança somente as atrasadas."""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from psycopg import sql


class Command(BaseCommand):
    help = 'Verifica sequências PostgreSQL; --apply avança IDs atrasados, sem reduzir sequências.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--database', default='default')

    def handle(self, *args, **options):
        conn = connections[options['database']]
        if conn.vendor != 'postgresql':
            raise CommandError('Este comando exige PostgreSQL.')
        tables = sorted({(m._meta.db_table, m._meta.pk.column)
                         for m in apps.get_models(include_auto_created=True)
                         if m._meta.managed and not m._meta.proxy
                         and m._meta.pk.get_internal_type() in ('AutoField', 'BigAutoField', 'SmallAutoField')})
        changed = 0
        with transaction.atomic(using=conn.alias), conn.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            for table, column in tables:
                if options['apply']:
                    cursor.execute(sql.SQL('LOCK TABLE {} IN ACCESS EXCLUSIVE MODE').format(sql.Identifier(table)))
                cursor.execute('SELECT pg_get_serial_sequence(%s, %s)', [table, column])
                seq = cursor.fetchone()[0]
                if not seq:
                    raise CommandError(f'Sequência ausente: {table}.{column}')
                cursor.execute('SELECT n.nspname, c.relname, s.seqincrement FROM pg_class c '
                               'JOIN pg_namespace n ON n.oid=c.relnamespace '
                               'JOIN pg_sequence s ON s.seqrelid=c.oid WHERE c.oid=%s::regclass', [seq])
                schema, name, increment = cursor.fetchone()
                if increment != 1:
                    raise CommandError(f'Incremento não suportado: {seq}')
                sequence = sql.Identifier(schema, name)
                cursor.execute(sql.SQL('SELECT last_value, is_called FROM {}').format(sequence))
                last, called = cursor.fetchone()
                cursor.execute(sql.SQL('SELECT MAX({}) FROM {}').format(sql.Identifier(column), sql.Identifier(table)))
                maximum = cursor.fetchone()[0]
                next_id = last + 1 if called else last
                if maximum is not None and next_id <= maximum:
                    changed += 1
                    self.stdout.write(f'{table}: próximo ID {next_id} -> {maximum + 1}')
                    if options['apply']:
                        # RESTART é transacional, ao contrário de setval(). Locks impedem INSERT concorrente.
                        cursor.execute(sql.SQL('ALTER SEQUENCE {} RESTART WITH {}').format(
                            sequence, sql.Literal(maximum + 1)))
        self.stdout.write(f'{changed} sequência(s) ' + ('corrigida(s).' if options['apply'] else 'atrasada(s); nenhuma alteração.'))
