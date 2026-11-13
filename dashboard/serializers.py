from rest_framework import serializers
from contratos.models import Contrato
from clientes.models import Parceiro
from usuario.models import Usuario


class CompetenciaSerializer(serializers.ModelSerializer):
    mes = serializers.IntegerField(source='ultimo_mes', min_value=1, max_value=12)
    ano = serializers.IntegerField(source='ultimo_ano', min_value=1900, max_value=9999)

    class Meta:
        model = Usuario
        fields = ('mes', 'ano')

    def update(self, instance, validated_data):
        instance.ultimo_mes = validated_data['ultimo_mes']
        instance.ultimo_ano = validated_data['ultimo_ano']
        instance.save(update_fields=['ultimo_mes', 'ultimo_ano'])
        return instance


class PeriodoSerializer(serializers.Serializer):
    mes = serializers.IntegerField(min_value=1, max_value=12)
    ano = serializers.IntegerField(min_value=1900, max_value=9999)
    pagina_alertas = serializers.IntegerField(min_value=1, default=1, max_value=1000000)


class AlertaSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source='cliente.instituicao', read_only=True)

    class Meta:
        model = Contrato
        fields = ('id', 'numero', 'cliente_nome', 'dt_data_final')
        read_only_fields = fields


class ParceiroResumoSerializer(serializers.ModelSerializer):
    clientes = serializers.IntegerField(read_only=True)
    percentual = serializers.SerializerMethodField()

    class Meta:
        model = Parceiro
        fields = ('id', 'instituicao', 'clientes', 'percentual')
        read_only_fields = fields

    def get_percentual(self, obj):
        from decimal import Decimal
        total = self.context['total_clientes']
        return str((Decimal(obj.clientes) * 100 / total).quantize(Decimal('0.01'))) if total else '0.00'


class ResumoSerializer(serializers.Serializer):
    # Não existe tabela do Dashboard: as projeções de entidades acima usam
    # ModelSerializer; este contrato reúne somente os agregados autorizados.
    empresa = serializers.IntegerField()
    mes = serializers.IntegerField()
    ano = serializers.IntegerField()
    atualizado_em = serializers.DateTimeField()
    permissoes = serializers.DictField(child=serializers.BooleanField())
    clientes = serializers.DictField(allow_null=True)
    notas = serializers.DictField(allow_null=True)
    receitas = serializers.DictField(allow_null=True)
    parceiros = serializers.DictField(allow_null=True)
    alertas = serializers.DictField(allow_null=True)
