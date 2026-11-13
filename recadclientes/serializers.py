from rest_framework import serializers
from conta.serializers import CleanSerializer
from servicos.serializers import clientes_visiveis
from .models import EntidadeRecad, UsuarioRecad, ContadorRecad, ControladorRecad, PrefeitoRecad, VicePrefeitoRecad


def entidades_visiveis(empresa, user):
    return EntidadeRecad.objects.filter(cliente__in=clientes_visiveis(empresa, user))


class EntidadeRecadSerializer(CleanSerializer):
    cliente_nome = serializers.CharField(source='cliente.instituicao', read_only=True)
    cidade_nome = serializers.CharField(source='cidade.descricao', read_only=True, default=None)
    uf_sigla = serializers.CharField(source='uf.sigla', read_only=True, default=None)

    class Meta:
        model = EntidadeRecad
        fields = ('id', 'cliente', 'cliente_nome', 'codigo', 'tipo', 'nome', 'uf', 'uf_sigla', 'cidade', 'cidade_nome', 'telefone', 'site', 'email')
        read_only_fields = ('id', 'cliente_nome', 'cidade_nome', 'uf_sigla')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        self.fields['cliente'].queryset = clientes_visiveis(self.context.get('empresa_id'), request.user if request else None)

    def validate_cliente(self, value):
        if self.instance and value.pk != self.instance.cliente_id:
            raise serializers.ValidationError('O cliente não pode ser alterado após o cadastro da entidade.')
        return value


class ResponsavelRecadSerializer(CleanSerializer):
    entidade_nome = serializers.CharField(source='entidade.nome', read_only=True)

    class Meta:
        fields = ('id', 'entidade', 'entidade_nome', 'nome_completo', 'telefone', 'email')
        read_only_fields = ('id', 'entidade_nome')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        self.fields['entidade'].queryset = entidades_visiveis(self.context.get('empresa_id'), request.user if request else None)


class UsuarioRecadSerializer(ResponsavelRecadSerializer):
    class Meta(ResponsavelRecadSerializer.Meta):
        model = UsuarioRecad
        fields = ResponsavelRecadSerializer.Meta.fields + ('cargo',)


class ContadorRecadSerializer(ResponsavelRecadSerializer):
    class Meta(ResponsavelRecadSerializer.Meta):
        model = ContadorRecad


class ControladorRecadSerializer(ResponsavelRecadSerializer):
    class Meta(ResponsavelRecadSerializer.Meta):
        model = ControladorRecad


class PrefeitoRecadSerializer(ResponsavelRecadSerializer):
    class Meta(ResponsavelRecadSerializer.Meta):
        model = PrefeitoRecad


class VicePrefeitoRecadSerializer(ResponsavelRecadSerializer):
    class Meta(ResponsavelRecadSerializer.Meta):
        model = VicePrefeitoRecad
