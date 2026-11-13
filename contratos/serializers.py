"""Contrato e seus itens/renovações são gravados como uma única unidade."""
from copy import copy
from decimal import Decimal
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from rest_framework import serializers
from clientes.models import Cliente
from produtos.models import Produto
from .models import Contrato, ContratoProduto, ContratoRenovacao


class ContratoProdutoSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False, min_value=1)
    produto_nome = serializers.SerializerMethodField()
    valor = serializers.DecimalField(max_digits=12, decimal_places=5, min_value=Decimal('0'))

    class Meta:
        model = ContratoProduto
        fields = ('id', 'produtos', 'produto_nome', 'valor')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['produtos'].queryset = Produto.objects.filter(empresa_id=self.context.get('empresa_id'))

    def validate(self, attrs):
        for field in ('produtos', 'valor'):
            if field not in attrs:
                raise serializers.ValidationError({field: 'Informe este campo em cada item enviado.'})
        return attrs

    def get_produto_nome(self, obj):
        return obj.produtos.descricao if obj.produtos.empresa_id == self.context.get('empresa_id') else None


class ContratoRenovacaoSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False, min_value=1)

    class Meta:
        model = ContratoRenovacao
        fields = ('id', 'dt_data_inicio', 'dt_data_final')

    def validate(self, attrs):
        for field in ('dt_data_inicio', 'dt_data_final'):
            if field not in attrs:
                raise serializers.ValidationError({field: 'Informe as duas datas da renovação.'})
        if attrs['dt_data_inicio'] > attrs['dt_data_final']:
            raise serializers.ValidationError({'dt_data_final': 'A data final deve ser igual ou posterior à inicial.'})
        return attrs


class ContratoResumoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source='cliente.instituicao', read_only=True)
    cliente_cnpj = serializers.CharField(source='cliente.cnpj', read_only=True)
    uf_nome = serializers.CharField(source='cliente.uf.sigla', read_only=True, default=None)
    tem_nota = serializers.SerializerMethodField()

    def get_tem_nota(self, obj):
        return obj.possui_nota if hasattr(obj, 'possui_nota') else obj.ContNotas.exists()

    class Meta:
        model = Contrato
        fields = ('id', 'empresa', 'cliente', 'cliente_nome', 'cliente_cnpj', 'uf_nome', 'numero',
                  'dia_nota', 'dt_data_contrato', 'dt_data_final', 'exercicio', 'objeto', 'observacoes',
                  'valor_bruto', 'perc_iss', 'perc_irpj', 'valor_iss', 'valor_irpj', 'valor_liquido',
                  'ativo', 'emitirnota', 'prestacao_municipio', 'tem_nota')
        read_only_fields = ('id', 'empresa')


class ContratoSerializer(ContratoResumoSerializer):
    itens = ContratoProdutoSerializer(many=True, source='produtosCont', required=False)
    renovacoes = ContratoRenovacaoSerializer(many=True, source='renovacao', required=False)
    notas = serializers.SerializerMethodField()
    valor_bruto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    perc_iss = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'))
    perc_irpj = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'))
    valor_iss = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    valor_irpj = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    valor_liquido = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    dia_nota = serializers.IntegerField(min_value=1, max_value=31)
    exercicio = serializers.IntegerField(min_value=1, max_value=9999)

    class Meta(ContratoResumoSerializer.Meta):
        fields = ContratoResumoSerializer.Meta.fields + ('itens', 'renovacoes', 'notas')
        extra_kwargs = {name: {'required': True, 'allow_null': False} for name in
                        ('numero', 'dt_data_contrato', 'dt_data_final', 'objeto')}
        extra_kwargs['observacoes'] = {'required': False, 'allow_blank': True, 'allow_null': True}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        clientes = Cliente.objects.filter(empresa_id=self.context.get('empresa_id'))
        request = self.context.get('request')
        if request and request.user.uf_id:
            clientes = clientes.filter(uf_id=request.user.uf_id)
        self.fields['cliente'].queryset = clientes
        self.fields['itens'].child.fields['produtos'].queryset = Produto.objects.filter(empresa_id=self.context.get('empresa_id'))

    def get_notas(self, obj):
        return [{'id': n.pk, 'numero': n.numero, 'competencia': n.competencia, 'exercicio': n.exercicio,
                 'dt_data_emissao': n.dt_data_emissao, 'dt_data_vencimento': n.dt_data_vencimento,
                 'dt_data_pagamento': n.dt_data_pagamento, 'valor_liquido': str(n.valor_liquido) if n.valor_liquido is not None else None}
                for n in obj.ContNotas.all() if n.empresa_id == self.context.get('empresa_id')]

    def validate(self, attrs):
        candidate = copy(self.instance) if self.instance else Contrato()
        candidate.empresa_id = self.context.get('empresa_id')
        for name, value in attrs.items():
            if name not in ('produtosCont', 'renovacao'):
                setattr(candidate, name, value)
        try:
            candidate.clean()
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        if self.instance and candidate.cliente_id != self.instance.cliente_id and self.instance.ContNotas.exists():
            raise serializers.ValidationError({'cliente': 'Não é possível trocar o cliente de um contrato com notas vinculadas.'})
        for source, label in (('produtosCont', 'itens'), ('renovacao', 'renovacoes')):
            if source not in attrs:
                continue
            if len(attrs[source]) > 200:
                raise serializers.ValidationError({label: 'Informe no máximo 200 registros por contrato.'})
            ids = [row['id'] for row in attrs[source] if 'id' in row]
            allowed = set(getattr(self.instance, source).values_list('id', flat=True)) if self.instance else set()
            if len(ids) != len(set(ids)) or not set(ids).issubset(allowed):
                raise serializers.ValidationError({label: 'Há IDs repetidos ou registros que não pertencem a este contrato.'})
        return attrs

    def _save_children(self, instance, source, values, model):
        if values is None:
            return
        manager = getattr(instance, source)
        keep = []
        for row in values:
            pk = row.pop('id', None)
            if pk:
                obj = manager.get(pk=pk)
                for name, value in row.items():
                    setattr(obj, name, value)
                obj.save()
            else:
                obj = model.objects.create(contrato=instance, **row)
            keep.append(obj.pk)
        manager.exclude(pk__in=keep).delete()

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop('produtosCont', [])
        renewals = validated_data.pop('renovacao', [])
        instance = super().create(validated_data)
        self._save_children(instance, 'produtosCont', items, ContratoProduto)
        self._save_children(instance, 'renovacao', renewals, ContratoRenovacao)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop('produtosCont', None)
        renewals = validated_data.pop('renovacao', None)
        instance = super().update(instance, validated_data)
        self._save_children(instance, 'produtosCont', items, ContratoProduto)
        self._save_children(instance, 'renovacao', renewals, ContratoRenovacao)
        return instance


class ContratoRelatorioSerializer(ContratoResumoSerializer):
    itens = ContratoProdutoSerializer(many=True, source='produtosCont', read_only=True)

    class Meta(ContratoResumoSerializer.Meta):
        fields = ContratoResumoSerializer.Meta.fields + ('itens',)


class CalculoContratoSerializer(serializers.Serializer):
    valor_bruto = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    perc_iss = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'))
    perc_irpj = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0'), max_value=Decimal('100'))

    def validate(self, attrs):
        if attrs['perc_iss'] + attrs['perc_irpj'] > 100:
            raise serializers.ValidationError('A soma dos percentuais não pode ultrapassar 100%.')
        return attrs
