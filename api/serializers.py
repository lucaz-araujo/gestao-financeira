from datetime import date
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework import serializers
from clientes.models import Cliente, Liberacao
from chaves.models import ChaveServico
from notas.models import Nota


class ASCIIField(serializers.CharField):
    def __init__(self, **kwargs):
        super().__init__(trim_whitespace=False, **kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not value.isascii() or any(ord(char) < 32 or ord(char) > 126 for char in value):
            raise serializers.ValidationError('Use caracteres ASCII imprimíveis.')
        return value


class AssinadaSerializer(serializers.Serializer):
    key = serializers.RegexField(r'^[0-9a-fA-F]{32}$', trim_whitespace=False, write_only=True)


class CodigosSerializer(AssinadaSerializer):
    codigo = ASCIIField(max_length=10)
    codigo_layout = ASCIIField(max_length=10)


class CompetenciaSerializer(CodigosSerializer):
    competencia = ASCIIField(max_length=6, min_length=6)

    def validate_competencia(self, value):
        if not value.isdigit() or not 1 <= int(value[:2]) <= 12 or not 1 <= int(value[2:]) <= 9999:
            raise serializers.ValidationError('Informe MMYYYY válido.')
        return value


class WebSerializer(CompetenciaSerializer):
    key = serializers.RegexField(r'^[0-9a-f]{64}$', trim_whitespace=False, write_only=True)


class BloqueioSerializer(CompetenciaSerializer):
    competencia = ASCIIField(max_length=6, min_length=4)

    def validate_competencia(self, value):
        if len(value) == 4 and value.isdigit() and 1 <= int(value) <= 9999:
            return value
        if len(value) != 6:
            raise serializers.ValidationError('Informe YYYY ou MMYYYY.')
        return super().validate_competencia(value)


class TransparenciaSerializer(CodigosSerializer):
    tipo = serializers.ChoiceField(choices=('1', '2'), default='1')


class ServicoSerializer(AssinadaSerializer):
    servico = ASCIIField(max_length=100)
    cnpj = ASCIIField(max_length=20)
    competencia = ASCIIField(max_length=6, min_length=6)
    validate_competencia = CompetenciaSerializer.validate_competencia


class RecadSerializer(CompetenciaSerializer):
    dados = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False, max_length=65536, write_only=True)


class MunicipioSerializer(serializers.Serializer):
    municipio = serializers.RegexField(r'^[0-9]{7}$', trim_whitespace=False)


class EntidadePublicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ('cnpj', 'instituicao', 'codigoentidade')
        read_only_fields = fields


class NotaLegadaSerializer(serializers.ModelSerializer):
    vencimento = serializers.SerializerMethodField()
    valor = serializers.DecimalField(source='valor_liquido', max_digits=10, decimal_places=2, allow_null=True, coerce_to_string=True)
    competencia = serializers.CharField(source='get_competencia_display')
    url = serializers.SerializerMethodField()

    class Meta:
        model = Nota
        fields = ('numero', 'vencimento', 'valor', 'competencia', 'url')
        read_only_fields = fields

    def get_vencimento(self, obj):
        return (obj.dt_data_vencimento or obj.dt_data_emissao).strftime('%d/%m/%Y')

    def get_url(self, obj):
        from django.conf import settings
        origin = settings.PUBLIC_APP_URL or 'http://gestao.layoutsistemas.com.br'
        return origin.rstrip('/') + '/notas/montanota/' + str(obj.pk) + '/'


class LiberacaoLegadaSerializer(serializers.ModelSerializer):
    usuario = serializers.CharField(source='usuario.username', default='', read_only=True)
    data_liberacao = serializers.SerializerMethodField()

    class Meta:
        model = Liberacao
        fields = ('usuario', 'data_liberacao')
        read_only_fields = fields

    def get_data_liberacao(self, obj):
        return DjangoJSONEncoder().default(obj.dt_liberacao)


class ChaveLegadaSerializer(LiberacaoLegadaSerializer):
    class Meta(LiberacaoLegadaSerializer.Meta):
        model = ChaveServico
