from copy import copy
from decimal import Decimal
from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers
from contabil.models import PlanoContas
from .models import Banco, Conta, Movimento, Transferencia
from .services import manual


class CleanSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        candidate = copy(self.instance) if self.instance else self.Meta.model()
        if hasattr(candidate, 'empresa_id'):
            candidate.empresa_id = self.context['empresa_id']
        for name, value in attrs.items():
            setattr(candidate, name, value)
        try:
            candidate.clean()
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


class BancoSerializer(CleanSerializer):
    class Meta:
        model = Banco
        fields = ('id', 'codigo', 'nome')
        read_only_fields = ('id',)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        for field in ('codigo', 'nome'):
            if field in attrs and Banco.objects.filter(**{field + '__iexact': attrs[field]}).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise serializers.ValidationError({field: 'Já existe um banco com este valor.'})
        return attrs


class ContaSerializer(CleanSerializer):
    banco_nome = serializers.CharField(source='banco.nome', read_only=True)
    banco_codigo = serializers.CharField(source='banco.codigo', read_only=True)
    plano_descricao = serializers.CharField(source='conta_contabil.descricao', read_only=True, default=None)
    class Meta:
        model = Conta
        fields = ('id', 'empresa', 'banco', 'banco_nome', 'banco_codigo', 'conta_contabil', 'plano_descricao', 'agencia', 'dv_agencia', 'numeroconta', 'dv_conta', 'descricao')
        read_only_fields = ('id', 'empresa')
        extra_kwargs = {'conta_contabil': {'required': False, 'allow_null': True}, 'dv_conta': {'required': False, 'allow_blank': True, 'allow_null': True}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['conta_contabil'].queryset = PlanoContas.objects.filter(empresa_id=self.context.get('empresa_id'))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        names = ['banco', 'agencia', 'dv_agencia', 'numeroconta', 'dv_conta']
        filters = {name: attrs.get(name, getattr(self.instance, name, None)) for name in names}
        if Conta.objects.filter(empresa_id=self.context['empresa_id'], **filters).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError({'numeroconta': 'Esta conta já está cadastrada nesta empresa.'})
        return attrs


class OperacaoSerializer(CleanSerializer):
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True, default=None)
    valor = serializers.DecimalField(max_digits=15, decimal_places=3, min_value=Decimal('0.001'))
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('conta', 'conta_origem', 'conta_destino'):
            if name in self.fields:
                self.fields[name].queryset = Conta.objects.filter(empresa_id=self.context.get('empresa_id'))


class MovimentoSerializer(OperacaoSerializer):
    conta_nome = serializers.CharField(source='conta.descricao', read_only=True)
    editavel = serializers.SerializerMethodField()
    class Meta:
        model = Movimento
        fields = ('id', 'empresa', 'conta', 'conta_nome', 'tipo_documento', 'nr_documento', 'dt_movimento', 'tipo_movimento', 'valor', 'usuario', 'usuario_nome', 'historico', 'receita', 'despesa', 'transferencia', 'editavel')
        read_only_fields = ('id', 'empresa', 'usuario', 'receita', 'despesa', 'transferencia')
        extra_kwargs = {name: {'required': False, 'allow_null': True, 'allow_blank': True} for name in ('nr_documento', 'historico')}

    def get_editavel(self, obj):
        return not (obj.receita_id or obj.despesa_id or obj.transferencia_id or obj.tipo_documento == 'TRA')

    def validate(self, attrs):
        if self.instance:
            manual(self.instance)
        if attrs.get('tipo_documento') == 'TRA':
            raise serializers.ValidationError({'tipo_documento': 'Use o cadastro de transferências para gerar os dois movimentos.'})
        return super().validate(attrs)


class TransferenciaSerializer(OperacaoSerializer):
    editavel = serializers.SerializerMethodField()

    def get_editavel(self, obj):
        return obj.par_consistente()

    origem_nome = serializers.CharField(source='conta_origem.descricao', read_only=True)
    destino_nome = serializers.CharField(source='conta_destino.descricao', read_only=True)
    class Meta:
        model = Transferencia
        fields = ('id', 'empresa', 'conta_origem', 'origem_nome', 'conta_destino', 'destino_nome', 'nr_documento', 'dt_movimento', 'valor', 'usuario', 'usuario_nome', 'historico', 'editavel')
        read_only_fields = ('id', 'empresa', 'usuario')
        extra_kwargs = {name: {'required': False, 'allow_null': True, 'allow_blank': True} for name in ('nr_documento', 'historico')}
