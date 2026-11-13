from rest_framework import serializers
from conta.serializers import CleanSerializer
from servicos.models import Servico
from servicos.serializers import clientes_visiveis
from .models import ChaveServico


class ChaveServicoSerializer(CleanSerializer):
    cliente_nome = serializers.CharField(source='cliente.instituicao',read_only=True)
    servico_nome = serializers.CharField(source='servico.descricao',read_only=True,default=None)
    usuario_nome = serializers.CharField(source='usuario.username',read_only=True,default=None)
    competencia = serializers.CharField(max_length=2)
    exercicio = serializers.IntegerField(min_value=1900,max_value=9999)
    class Meta:
        model = ChaveServico
        fields = ('id','cliente','cliente_nome','servico','servico_nome','competencia','exercicio','dt_liberacao','chave','usuario','usuario_nome')
        read_only_fields = ('id','dt_liberacao','chave','usuario')
        extra_kwargs = {'servico':{'required':True,'allow_null':False}}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        request = self.context.get('request')
        company = self.context.get('empresa_id')
        clients = clientes_visiveis(company,request.user if request else None)
        self.fields['cliente'].queryset = clients
        self.fields['servico'].queryset = Servico.objects.filter(empresa_id=company,cliente__in=clients)
    def validate_competencia(self,value):
        if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 12:
            raise serializers.ValidationError('Informe uma competência de 01 a 12.')
        return value.zfill(2)
