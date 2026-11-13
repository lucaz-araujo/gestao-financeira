"""Auditoria de transferências sem alterar o livro financeiro."""
import csv
import os
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from conta.models import Transferencia


class Command(BaseCommand):
    help = 'Lista inconsistências entre transferências e seus movimentos, sem corrigir registros.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='CSV privado com as transferências que precisam de conciliação.')

    def handle(self, *args, **options):
        records = []
        total = 0
        for transfer in Transferencia.objects.prefetch_related('transferencia').order_by('pk').iterator(chunk_size=500):
            total += 1
            legs = list(transfer.transferencia.all())
            if not transfer.par_consistente(legs):
                records.append([transfer.pk, transfer.empresa_id, transfer.dt_movimento, transfer.conta_origem_id,
                    transfer.conta_destino_id, transfer.valor, len(legs),
                    sum((m.valor for m in legs if m.tipo_movimento == 'D'), Decimal('0')),
                    sum((m.valor for m in legs if m.tipo_movimento == 'C'), Decimal('0'))])
        if options['output']:
            path = Path(options['output'])
            try:
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, 'w', newline='', encoding='utf-8-sig') as stream:
                    writer = csv.writer(stream, delimiter=';')
                    writer.writerow(['transferencia_id', 'empresa_id', 'data', 'origem_id', 'destino_id', 'valor', 'quantidade_movimentos', 'total_debitos', 'total_creditos'])
                    writer.writerows(records)
            except OSError as error:
                raise CommandError('Não foi possível criar o CSV. Escolha um arquivo novo em uma pasta existente.') from error
            self.stdout.write(f'CSV privado criado: {path}')
        self.stdout.write(f'Transferências verificadas: {total}; conciliação necessária: {len(records)}. Nenhum registro financeiro foi alterado.')
