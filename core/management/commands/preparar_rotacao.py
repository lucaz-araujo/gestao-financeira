"""Gera candidatos privados; nunca ativa chaves nem altera credenciais de consumidores."""
import json
import os
import secrets
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Prepara chaves fortes em arquivo privado, preservando os fallbacks fiscais. Não ativa a rotação.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        data = {
            'secret_key_nova': secrets.token_urlsafe(64),
            'secret_key_fallbacks_durante_transicao': list(dict.fromkeys([settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS])),
            'api_secret_key_nova': secrets.token_hex(48),
            'ativado': False,
            'instrucoes': 'Ativar o segredo de integração somente após atualizar os consumidores. Preservar os fallbacks até recifrar as credenciais fiscais e validar a recuperação. Nenhuma credencial atual foi alterada.',
        }
        path = Path(options['output'])
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as stream:
                json.dump(data, stream, indent=2, ensure_ascii=False)
        except OSError:
            raise CommandError('Use um caminho privado novo e gravável. Nenhum arquivo existente foi substituído.')
        self.stdout.write('Candidatos de rotação preparados em arquivo privado. Não ativados; credenciais atuais preservadas.')
