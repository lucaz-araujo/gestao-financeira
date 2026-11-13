import json
import os
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.core.mail import get_connection
from core.operations import deployment_status, legacy_audit, fiscal_audit


class Command(BaseCommand):
    help = 'Audita publicação, SMTP, fiscal e dados legados, sem alterar o banco ou enviar e-mail.'

    def add_arguments(self, parser):
        parser.add_argument('--report', help='Novo arquivo JSON privado; não sobrescreve arquivos existentes.')
        parser.add_argument('--smtp', action='store_true', help='Testa somente conexão/TLS/autenticação SMTP, sem mensagem.')
        parser.add_argument('--fail-on-pending', action='store_true')

    def handle(self, *args, **options):
        with transaction.atomic():
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION READ ONLY')
            report = {'publicacao': deployment_status(), 'legado': legacy_audit(), 'fiscal': fiscal_audit()}
        if options['smtp']:
            from django.conf import settings
            if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend' or not settings.EMAIL_HOST:
                report['smtp_conexao'] = False
            else:
                transport = get_connection(fail_silently=False)
                try:
                    report['smtp_conexao'] = bool(transport.open())
                except Exception:
                    report['smtp_conexao'] = False
                finally:
                    try:
                        transport.close()
                    except Exception:
                        report['smtp_conexao'] = False
        summary = {
            'publicacao': report['publicacao'],
            'grupos_clientes_ambiguos': len(report['legado']['identidades_ambiguas']),
            'periodos_para_conciliar': len(report['legado']['periodos_com_multiplas_liberacoes']),
            'liberacoes_para_revisar': len(report['legado']['liberacoes_com_codigos_diferentes_do_cadastro_atual_ids']),
            'empresas_fiscais_verificadas': len(report['fiscal']),
            'empresas_fiscais_pendentes': sum(not item['disponivel'] for item in report['fiscal']),
        }
        if 'smtp_conexao' in report:
            summary['smtp_conexao'] = report['smtp_conexao']
        if options['report']:
            path = Path(options['report'])
            path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as stream:
                    json.dump(report, stream, ensure_ascii=False, indent=2)
            except OSError:
                raise CommandError('Não foi possível criar o relatório privado; use um caminho novo e gravável.')
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
        pending = not all(report['publicacao'].values()) or summary['grupos_clientes_ambiguos'] or summary['periodos_para_conciliar'] or summary['liberacoes_para_revisar'] or not report['fiscal'] or summary['empresas_fiscais_pendentes'] or ('smtp_conexao' in report and not report['smtp_conexao'])
        if options['fail_on_pending'] and pending:
            raise CommandError('Há pendências operacionais; consulte o relatório privado. Nenhuma alteração foi aplicada.')
