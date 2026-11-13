import re
from clientes.validador import validar_cnpj


def cnpj_valido(value):
    digits = re.sub(r'\D','',str(value or ''))
    return len(digits)==14 and digits.isascii() and len(set(digits))>1 and bool(validar_cnpj(value))
