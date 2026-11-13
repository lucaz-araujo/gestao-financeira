from decimal import Decimal
from rest_framework import serializers
from conta.serializers import CleanSerializer
from notas.gateway import certificate_path
from .models import Ambiente


class AmbienteSerializer(CleanSerializer):
    senha=serializers.CharField(write_only=True,required=False,allow_blank=True,max_length=256,trim_whitespace=False)
    certificado=serializers.FileField(write_only=True,required=False)
    confirmar_producao=serializers.BooleanField(write_only=True,required=False,default=False)
    empresa_nome=serializers.CharField(source='empresa.razao',read_only=True)
    certificado_cadastrado=serializers.SerializerMethodField()
    certificado_disponivel=serializers.SerializerMethodField()
    senha_cadastrada=serializers.SerializerMethodField()
    aliquota_iss=serializers.DecimalField(max_digits=7,decimal_places=4,min_value=Decimal('0'),max_value=Decimal('100'),allow_null=True,required=False)
    class Meta:
        model=Ambiente
        fields=('id','empresa','empresa_nome','descricao','certificado','senha','certificado_cadastrado','certificado_disponivel','senha_cadastrada','homologacao','confirmar_producao','aliquota_iss','numero_lote','numero_rps','coigo_servico','codigo_cnae','codigo_tributacao_municipio','descr_tributacao_municipio')
        read_only_fields=('id','empresa','numero_lote','numero_rps')
        extra_kwargs={'homologacao':{'default':True}}
    def get_certificado_cadastrado(self,obj):return bool(obj.certificado)
    def get_certificado_disponivel(self,obj):return certificate_path(obj) is not None
    def get_senha_cadastrada(self,obj):return bool(obj.senha)
    def validate_certificado(self,value):
        if value.size>5*1024*1024:raise serializers.ValidationError('O certificado deve ter até 5 MB.')
        return value
    def validate(self,attrs):
        if any(field in self.initial_data for field in ('numero_lote','numero_rps')):
            raise serializers.ValidationError({'sequencias':'Use a ação específica de ajuste de sequências.'})
        super().validate({k:v for k,v in attrs.items() if k not in ('senha','certificado','confirmar_producao')})
        return attrs
