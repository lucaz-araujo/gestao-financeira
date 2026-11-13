from decimal import Decimal
from rest_framework import serializers
from conta.serializers import CleanSerializer
from .models import PlanoContas, CentroCusto, TipoDespesa, Lancamentos


class PlanoSerializer(CleanSerializer):
    class Meta:
        model = PlanoContas
        fields = ('id', 'empresa', 'conta', 'descricao', 'tipo', 'codigo')
        read_only_fields = ('id', 'empresa')
        extra_kwargs = {'tipo': {'required': False, 'allow_null': True}, 'codigo': {'required': False, 'allow_null': True, 'allow_blank': True}}


class VinculoSerializer(CleanSerializer):
    conta_nome = serializers.CharField(source='conta.descricao', read_only=True, default=None)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['conta'].queryset = PlanoContas.objects.filter(empresa_id=self.context.get('empresa_id'))


class CentroSerializer(VinculoSerializer):
    class Meta:
        model = CentroCusto
        fields = ('id', 'empresa', 'codigo', 'descricao', 'conta', 'conta_nome')
        read_only_fields = ('id', 'empresa')
        extra_kwargs = {'conta': {'required': False, 'allow_null': True}}


class TipoSerializer(VinculoSerializer):
    compartilhado = serializers.SerializerMethodField()
    def get_compartilhado(self, obj):
        return obj.conta_id is None
    class Meta:
        model = TipoDespesa
        fields = ('id', 'codigo', 'descricao', 'conta', 'conta_nome', 'compartilhado')
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get('conta', self.instance.conta if self.instance else None):
            raise serializers.ValidationError({'conta': 'Vincule o tipo a um plano da empresa. Tipos compartilhados antigos são de consulta.'})
        return attrs


class LancamentoSerializer(CleanSerializer):
    valor = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('.01'))
    dt_data = serializers.DateTimeField(required=True, allow_null=False)
    tipo = serializers.ChoiceField(choices=['C', 'D'], required=True)
    origem_nome = serializers.CharField(source='conta_origem.descricao', read_only=True)
    destino_nome = serializers.CharField(source='conta_destino.descricao', read_only=True)
    class Meta:
        model = Lancamentos
        fields = ('id', 'dt_data', 'tipo', 'conta_origem', 'origem_nome', 'conta_destino', 'destino_nome', 'valor', 'descricao')
        extra_kwargs = {field: {'required': True, 'allow_null': False} for field in ('conta_origem', 'conta_destino', 'descricao')}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ('conta_origem', 'conta_destino'):
            self.fields[field].queryset = PlanoContas.objects.filter(empresa_id=self.context.get('empresa_id'))
