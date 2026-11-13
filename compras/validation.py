from django.core.exceptions import ValidationError
from clientes.validador import validar_cnpj, validar_cpf


def fornecedor_limpo(obj):
    errors = {}
    for field, validator in [('cnpj',validar_cnpj),('cpf',validar_cpf),('resp_cpf',validar_cpf)]:
        value = getattr(obj,field)
        if value and not validator(value): errors[field] = 'Documento inválido.'
    if obj.cpf and obj.cnpj: errors['cnpj'] = 'Informe CPF ou CNPJ, separadamente.'
    if obj.cidade_id and (not obj.uf_id or obj.cidade.uf_id != obj.uf_id): errors['cidade'] = 'O município deve pertencer à UF.'
    if errors: raise ValidationError(errors)


def item_limpo(obj):
    if obj.unidade_id and obj.unidade.empresa_id != obj.empresa_id:
        raise ValidationError({'unidade':'A unidade deve pertencer à empresa do item.'})


def solicitacao_limpa(obj):
    errors = {}
    if obj.centro_custo_id and obj.centro_custo.empresa_id != obj.empresa_id:
        errors['centro_custo'] = 'Centro de custo de outra empresa.'
    if obj.tipo_despesa_id and obj.tipo_despesa.conta_id and obj.tipo_despesa.conta.empresa_id != obj.empresa_id:
        errors['tipo_despesa'] = 'Tipo de despesa de outra empresa.'
    if errors: raise ValidationError(errors)


def orcamento_limpo(obj):
    if obj.fornecedor_id and obj.solicitacao_id and (obj.fornecedor.empresa_id != obj.empresa_id or obj.solicitacao.empresa_id != obj.empresa_id):
        raise ValidationError({'fornecedor':'Fornecedor e solicitação devem pertencer à empresa do orçamento.'})


def linha_limpa(obj):
    parent = obj.orcamento if hasattr(obj,'menor_preco') else obj.solicitacao
    errors = {}
    if obj.item_id and (obj.item.empresa_id != parent.empresa_id or obj.item.unidade.empresa_id != parent.empresa_id):
        errors['item'] = 'Item ou unidade de outra empresa.'
    if obj.quantidade is None or obj.quantidade <= 0: errors['quantidade'] = 'Informe quantidade positiva.'
    if obj.valor is None or obj.valor < 0: errors['valor'] = 'Informe valor não negativo.'
    if errors: raise ValidationError(errors)
