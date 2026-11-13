import re
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from conta.serializers import CleanSerializer
from servicos.serializers import clientes_visiveis
from .models import Contato, Email, Telefone


class EmailSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False, min_value=1)
    class Meta:
        model = Email
        fields = ('id','email')
    def validate(self, attrs):
        if not attrs.get('email'): raise serializers.ValidationError({'email':'Informe o e-mail.'})
        return attrs


class TelefoneSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False, min_value=1)
    class Meta:
        model = Telefone
        fields = ('id','fone')
    def validate(self, attrs):
        phone = attrs.get('fone','')
        if not re.fullmatch(r'[+\d() .-]+',phone) or not 8 <= len(re.sub(r'\D','',phone)) <= 15:
            raise serializers.ValidationError({'fone':'Informe um telefone com 8 a 15 dígitos, incluindo DDD quando necessário.'})
        return attrs


class ContatoSerializer(CleanSerializer):
    emails = EmailSerializer(many=True,source='Emails',required=False)
    telefones = TelefoneSerializer(many=True,source='Telefones',required=False)
    cliente_nome = serializers.CharField(source='cliente.instituicao',read_only=True)
    cidade_nome = serializers.CharField(source='cidade.descricao',read_only=True,default=None)
    uf_sigla = serializers.CharField(source='uf.sigla',read_only=True,default=None)
    class Meta:
        model = Contato
        fields = ('id','cliente','cliente_nome','nome','cargo','logradouro','bairro','cidade','cidade_nome','uf','uf_sigla','emails','telefones')
        extra_kwargs = {'cliente':{'required':True,'allow_null':False},'nome':{'required':True,'allow_null':False,'allow_blank':False},
                        'cidade':{'required':False,'allow_null':True},'uf':{'required':False,'allow_null':True}}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        request = self.context.get('request')
        self.fields['cliente'].queryset = clientes_visiveis(self.context.get('empresa_id'),request.user if request else None)
    def validate(self, attrs):
        user = self.context['request'].user
        for source,model,field in [('Emails','email','email'),('Telefones','telefone','fone')]:
            if source in attrs:
                if not user.has_perm('agenda.view_'+model): raise PermissionDenied('Sem permissão para consultar/alterar '+model+'.')
                rows = attrs[source]
                if len(rows)>50: raise serializers.ValidationError({source:'Limite de 50 registros por contato.'})
                ids = [row['id'] for row in rows if 'id' in row]
                values = [(re.sub(r'\D','',row[field]) if field=='fone' else row[field].casefold()) for row in rows]
                if len(set(ids))!=len(ids) or len(set(values))!=len(values):
                    raise serializers.ValidationError({source:'Não repita registros, e-mails ou telefones.'})
        super().validate({k:v for k,v in attrs.items() if k not in ('Emails','Telefones')})
        return attrs
    def to_representation(self,instance):
        result = super().to_representation(instance)
        user = self.context['request'].user
        for field,model in [('emails','email'),('telefones','telefone')]:
            if not user.has_perm('agenda.view_'+model): result.pop(field,None)
        return result
