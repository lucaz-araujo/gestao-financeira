from conta.serializers import CleanSerializer
from rest_framework import serializers
from clientes.models import Cliente
from .models import Servico


def clientes_visiveis(empresa, usuario):
    qs = Cliente.objects.filter(empresa_id=empresa)
    if usuario and usuario.uf_id:
        qs = qs.filter(uf_id=usuario.uf_id)
    return qs


class ServicoSerializer(CleanSerializer):
    cliente_nome = serializers.CharField(source='cliente.instituicao', read_only=True)
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True, default=None)
    class Meta:
        model = Servico
        fields = ('id', 'empresa', 'cliente', 'cliente_nome', 'descricao', 'usuario', 'usuario_nome')
        read_only_fields = ('id', 'empresa', 'usuario')
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        self.fields['cliente'].queryset = clientes_visiveis(self.context.get('empresa_id'), request.user if request else None)
