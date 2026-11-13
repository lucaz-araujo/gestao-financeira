import uuid
from rest_framework import serializers
from conta.serializers import CleanSerializer
from .models import Empresa


class EmpresaSerializer(CleanSerializer):
    cnpj_valido = serializers.SerializerMethodField()
    def get_cnpj_valido(self,obj):
        from .validation import cnpj_valido
        return cnpj_valido(obj.cnpj)

    logo = serializers.ImageField(required=False)
    remover_logo = serializers.BooleanField(write_only=True,required=False,default=False)
    cidade_nome = serializers.CharField(source='cidade.descricao',read_only=True,default=None)
    uf_sigla = serializers.CharField(source='uf.sigla',read_only=True,default=None)
    class Meta:
        model = Empresa
        fields = ('id','cnpj','cnpj_valido','inscricao_municipal','razao','logo','logo_nome','uf','uf_sigla','cidade','cidade_nome','remover_logo')
        extra_kwargs = {'logo_nome':{'required':False,'allow_blank':True},'uf':{'required':True,'allow_null':False},'cidade':{'required':True,'allow_null':False}}
    def validate_logo(self,value):
        if value.size>5*1024*1024:
            raise serializers.ValidationError('A logo deve ter até 5 MB.')
        extension = {'PNG':'png','JPEG':'jpg','WEBP':'webp'}.get(value.image.format)
        if not extension:
            raise serializers.ValidationError('Use uma imagem PNG, JPEG ou WebP.')
        # O nome e extensão são gerados a partir do conteúdo validado da imagem.
        value.name = f'{uuid.uuid4().hex}.{extension}'
        return value
    def validate(self,attrs):
        if attrs.get('logo') and attrs.get('remover_logo'):
            raise serializers.ValidationError({'logo':'Escolha enviar uma logo ou remover a atual.'})
        super().validate({k:v for k,v in attrs.items() if k!='remover_logo'})
        return attrs
    def create(self,validated_data):
        validated_data.pop('remover_logo',None)
        return super().create(validated_data)
    def update(self,instance,validated_data):
        remove = validated_data.pop('remover_logo',False)
        if remove:validated_data['logo']=''
        return super().update(instance,validated_data)
