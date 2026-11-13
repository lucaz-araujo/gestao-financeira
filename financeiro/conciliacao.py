"""Prévia sem gravação: CSV explícito ou TXT legado do BB; confirmação com assinatura."""
import csv
import hashlib
import io
import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.core import signing
from rest_framework.exceptions import ValidationError

SALT = 'financeiro.conciliacao.v1'
# Mesmo formato posicional do importador anterior, sem gravar o arquivo recebido no servidor.
BB = re.compile(r'(?P<data>\d{2}/\d{2}/\d{4})\s*\d{4}\s*\d{5}\s*(?P<historico>.{28})\s(?P<documento>.{26,28}?)\s*(?P<valor>\d[\d.]*,\d{2})\s+C\s+', re.MULTILINE)


def previsualizar(file, company, user):
    if not file or file.size > 2 * 1024 * 1024:
        raise ValidationError({'extrato': 'Envie um extrato CSV ou TXT de até 2 MB.'})
    raw = file.read()
    try:
        content = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        content = raw.decode('latin1')
    digest = hashlib.sha256(raw).hexdigest()
    if file.name.lower().endswith('.csv'):
        reader = csv.DictReader(io.StringIO(content), delimiter=';')
        if not reader.fieldnames or not {'data', 'valor', 'documento'}.issubset(reader.fieldnames):
            raise ValidationError({'extrato': 'CSV: use as colunas data;valor;documento;historico. Datas DD/MM/AAAA e valores 1.234,56.'})
        source = list(reader)
    elif file.name.lower().endswith('.txt'):
        source = [match.groupdict() for match in BB.finditer(content)]
    else:
        raise ValidationError({'extrato': 'Formatos aceitos: CSV delimitado por ponto e vírgula ou TXT do BB.'})
    if not source or len(source) > 200:
        raise ValidationError({'extrato': 'O arquivo deve conter de 1 a 200 créditos reconhecíveis. Divida extratos maiores.'})
    result = []
    for index, row in enumerate(source):
        try:
            day = datetime.strptime(row['data'].strip(), '%d/%m/%Y').date().isoformat()
            amount = Decimal(row['valor'].strip().replace('.', '').replace(',', '.'))
            if not amount.is_finite() or amount <= 0 or amount >= Decimal('100000000') or amount != amount.quantize(Decimal('.01')):
                raise ValueError
        except (ValueError, InvalidOperation, KeyError, AttributeError):
            raise ValidationError({'extrato': f'Linha {index+2}: data ou valor inválido.'})
        payload = {'empresa': company, 'usuario': user, 'linha': index, 'arquivo': digest,
                   'dt_pagamento': day, 'valor': str(amount.quantize(Decimal('.01'))),
                   'documento': (row.get('documento') or '').strip()[:100], 'historico': (row.get('historico') or '').strip()[:200]}
        result.append({**payload, 'token': signing.dumps(payload, salt=SALT, compress=True)})
    return {'results': result, 'detail': 'Prévia: nenhum lançamento foi gravado. Vincule apenas créditos conferidos.'}


def validar_linhas(items, company, user):
    if not isinstance(items, list) or not 1 <= len(items) <= 200:
        raise ValidationError({'itens': 'Selecione de 1 a 200 linhas.'})
    seen, results = set(), []
    for item in items:
        try:
            payload = signing.loads(item['token'], salt=SALT, max_age=1800)
            if payload['empresa'] != company or payload['usuario'] != user:
                raise ValueError
            key = uuid.uuid5(uuid.NAMESPACE_URL, f"financeiro:{company}:{payload['arquivo']}:{payload['linha']}")
            if key in seen:
                raise ValueError
            seen.add(key)
            document = int(item['receita'])
            if document < 1:
                raise ValueError
        except (signing.BadSignature, KeyError, ValueError, TypeError):
            raise ValidationError({'itens': 'Prévia inválida, expirada ou linha repetida. Importe o arquivo novamente.'})
        results.append({'receita': document, 'idempotencia': key, 'valor': payload['valor'],
                        'dt_pagamento': payload['dt_pagamento'], 'obs': 'Conciliação: '+payload['documento'][:180]})
    return results
