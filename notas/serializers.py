from copy import copy
from decimal import Decimal
from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers
from contratos.models import Contrato
from .models import Nota, OperacaoFiscal


class OperacaoFiscalSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = OperacaoFiscal
        fields = ('id', 'acao', 'estado', 'resultado', 'criada_em', 'atualizada_em', 'usuario_nome')
        read_only_fields = fields


class NotaSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source='contrato.cliente.instituicao', read_only=True)
    contrato_numero = serializers.CharField(source='contrato.numero', read_only=True)
    cliente_cnpj = serializers.CharField(source='contrato.cliente.cnpj', read_only=True)
    cidade_nome = serializers.CharField(source='cidade.descricao', read_only=True, default=None)
    uf_nome = serializers.CharField(source='uf.sigla', read_only=True, default=None)
    estado_fiscal = serializers.CharField(read_only=True)
    tem_operacoes = serializers.SerializerMethodField()
    tem_financeiro = serializers.SerializerMethodField()
    competencia = serializers.IntegerField(min_value=1, max_value=12)
    exercicio = serializers.IntegerField(min_value=1, max_value=9999)
    valor_bruto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    imposto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    aliq_imposto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'))
    valor_liquido = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))

    class Meta:
        model = Nota
        fields = ('id', 'empresa', 'contrato', 'contrato_numero', 'cliente_nome', 'cliente_cnpj', 'numero',
                  'dt_data_emissao', 'competencia', 'exercicio', 'valor_bruto', 'imposto', 'aliq_imposto', 'valor_liquido',
                  'dt_data_vencimento', 'dt_data_pagamento', 'texto_nota', 'ja_enviou', 'ja_enviou_NFSE', 'dt_data_envio',
                  'cidade', 'uf', 'cidade_nome', 'uf_nome', 'coigo_servico', 'codigo_cnae', 'codigo_tributacao_municipio',
                  'descr_tributacao_municipio', 'protocolo_envio', 'protocolo_recebimento', 'dt_data_envio_sefaz',
                  'dt_data_autorizacao', 'numero_lote', 'numero_rps', 'prot_envio_can', 'dt_data_envio_can',
                  'cancelada_em', 'decimo_terceiro', 'estado_fiscal', 'tem_financeiro', 'tem_operacoes')
        read_only_fields = ('id', 'empresa', 'dt_data_pagamento', 'ja_enviou', 'ja_enviou_NFSE', 'dt_data_envio',
                            'protocolo_envio', 'protocolo_recebimento', 'dt_data_envio_sefaz', 'dt_data_autorizacao',
                            'numero_lote', 'numero_rps', 'prot_envio_can', 'dt_data_envio_can', 'cancelada_em')
        extra_kwargs = {'texto_nota': {'required': True, 'allow_null': False, 'allow_blank': False},
                        'numero': {'required': False, 'allow_null': True, 'allow_blank': True}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Contrato.objects.filter(empresa_id=self.context.get('empresa_id'), cliente__empresa_id=self.context.get('empresa_id'))
        request = self.context.get('request')
        if request and request.user.uf_id:
            qs = qs.filter(cliente__uf_id=request.user.uf_id)
        self.fields['contrato'].queryset = qs

    def get_tem_operacoes(self, obj):
        return bool(obj.operacoes.all())

    def get_tem_financeiro(self, obj):
        return bool(obj.docreceitas.all())

    def validate(self, attrs):
        if self.instance and (self.instance.estado_fiscal != 'rascunho' or self.instance.docreceitas.exists() or self.instance.operacoes.exists()):
            raise serializers.ValidationError('Somente rascunhos sem financeiro ou histórico de operações podem ser editados.')
        obj = copy(self.instance) if self.instance else Nota()
        obj.empresa_id = self.context.get('empresa_id')
        for key, value in attrs.items():
            setattr(obj, key, value)
        try:
            obj.clean()
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


class GeracaoNotasSerializer(serializers.Serializer):
    contratos = serializers.ListField(child=serializers.IntegerField(min_value=1), min_length=1, max_length=100)
    competencia = serializers.IntegerField(min_value=1, max_value=12)
    exercicio = serializers.IntegerField(min_value=1, max_value=9999)
    decimo_terceiro = serializers.BooleanField(default=False)

    def validate_contratos(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError('Não repita contratos na seleção.')
        return value


class AcaoFiscalSerializer(serializers.Serializer):
    confirmar = serializers.BooleanField()
    justificativa = serializers.CharField(required=False, max_length=500, allow_blank=True)

    def validate_confirmar(self, value):
        if not value:
            raise serializers.ValidationError('Confirme explicitamente a operação.')
        return value
