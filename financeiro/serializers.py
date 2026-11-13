from decimal import Decimal
from django.db.models import Q
from rest_framework import serializers
from conta.models import Conta
from conta.serializers import CleanSerializer
from clientes.models import Cliente
from compras.models import Fornecedor
from contabil.models import CentroCusto, TipoDespesa
from notas.models import Nota
from .models import DocReceita, DocDespesa, RecReceita, PagDespesa, FechamentoCaixa, Analise


def clientes_visiveis(empresa, usuario):
    qs = Cliente.objects.filter(empresa_id=empresa)
    if usuario and usuario.uf_id:
        qs = qs.filter(uf_id=usuario.uf_id)
    return qs


class DocumentoSerializer(CleanSerializer):
    valor = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    total_baixado = serializers.DecimalField(source='_total', max_digits=15, decimal_places=2, read_only=True)
    saldo = serializers.SerializerMethodField()
    situacao_atual = serializers.SerializerMethodField()
    usuario_nome = serializers.CharField(source='user_registro.username', read_only=True)
    def get_saldo(self, obj):
        return str(obj.valor - obj._total)
    def get_situacao_atual(self, obj):
        from django.utils import timezone
        return 'Quitado' if obj._total >= obj.valor else 'Vencido' if obj.dt_vencimento < timezone.localdate() else 'Aberto'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.context.get('empresa_id')
        request = self.context.get('request')
        customers = clientes_visiveis(company, request.user if request else None)
        relations = {'cliente': customers, 'nota': Nota.objects.filter(empresa_id=company, contrato__cliente__in=customers),
            'fornecedor': Fornecedor.objects.filter(empresa_id=company), 'centro_custo': CentroCusto.objects.filter(empresa_id=company),
            'tipo_despesa': TipoDespesa.objects.filter(Q(conta__isnull=True) | Q(conta__empresa_id=company))}
        for field, qs in relations.items():
            if field in self.fields:
                self.fields[field].queryset = qs


class DocReceitaSerializer(DocumentoSerializer):
    parte_nome = serializers.CharField(source='cliente.instituicao', read_only=True)
    class Meta:
        model = DocReceita
        fields = ('id', 'empresa', 'cliente', 'parte_nome', 'nota', 'numero', 'descricao', 'dt_vencimento', 'valor',
                  'valor_recebido', 'situacao', 'total_baixado', 'saldo', 'situacao_atual', 'dt_registro', 'user_registro', 'usuario_nome')
        read_only_fields = ('empresa', 'valor_recebido', 'situacao', 'dt_registro', 'user_registro')


class DocDespesaSerializer(DocumentoSerializer):
    parte_nome = serializers.CharField(source='fornecedor.instituicao', read_only=True)
    centro_nome = serializers.CharField(source='centro_custo.descricao', read_only=True, default=None)
    tipo_nome = serializers.CharField(source='tipo_despesa.descricao', read_only=True, default=None)
    class Meta:
        model = DocDespesa
        fields = ('id', 'empresa', 'fornecedor', 'parte_nome', 'numero', 'descricao', 'dt_vencimento', 'valor', 'valor_pago',
                  'situacao', 'total_baixado', 'saldo', 'situacao_atual', 'tipo_despesa', 'tipo_nome', 'centro_custo', 'centro_nome', 'dt_registro', 'user_registro', 'usuario_nome')
        read_only_fields = ('empresa', 'valor_pago', 'situacao', 'dt_registro', 'user_registro')
        extra_kwargs = {name: {'required': False, 'allow_null': True} for name in ('tipo_despesa', 'centro_custo')}


class BaixaSerializer(CleanSerializer):
    idempotencia = serializers.UUIDField(write_only=True, required=True)
    valor = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    conta_nome = serializers.CharField(source='conta.descricao', read_only=True, default=None)
    usuario_nome = serializers.CharField(source='user_registro.username', read_only=True)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['conta'].queryset = Conta.objects.filter(empresa_id=self.context.get('empresa_id'))
        self.fields['conta'].allow_null = False
    def validate(self, attrs):
        candidate = self.Meta.model(**{k: v for k, v in attrs.items() if k != 'idempotencia'})
        setattr(candidate, 'receita' if self.Meta.model == RecReceita else 'despesa', self.context['documento'])
        from django.core.exceptions import ValidationError
        try:
            candidate.clean()
        except ValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


class RecReceitaSerializer(BaixaSerializer):
    class Meta:
        model = RecReceita
        fields = ('id', 'receita', 'conta', 'conta_nome', 'dt_pagamento', 'valor', 'obs', 'user_registro', 'usuario_nome', 'dt_registro', 'idempotencia')
        read_only_fields = ('receita', 'user_registro', 'dt_registro')


class PagDespesaSerializer(BaixaSerializer):
    class Meta:
        model = PagDespesa
        fields = ('id', 'despesa', 'conta', 'conta_nome', 'forma_pagamento', 'numero_cheque', 'dt_pagamento', 'valor', 'obs', 'user_registro', 'usuario_nome', 'dt_registro', 'idempotencia')
        read_only_fields = ('despesa', 'user_registro', 'dt_registro')


class FechamentoSerializer(serializers.ModelSerializer):
    conta_nome = serializers.CharField(source='conta.descricao', read_only=True)
    usuario_nome = serializers.CharField(source='user_fechamento.username', read_only=True)
    class Meta:
        model = FechamentoCaixa
        fields = ('id', 'empresa', 'conta', 'conta_nome', 'data', 'hora', 'receitas', 'despesas', 'saldo', 'saldo_anterior', 'user_fechamento', 'usuario_nome')
        read_only_fields = fields


class AnaliseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Analise
        fields = '__all__'
