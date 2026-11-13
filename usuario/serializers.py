import re
import uuid
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import Permission
from empresa.models import Empresa
from rest_framework import serializers
from .models import Usuario
from clientes.validador import validar_cpf


class UsuarioSerializer(serializers.ModelSerializer):
    email_password=serializers.CharField(write_only=True,required=False,max_length=256,trim_whitespace=False)
    avatar=serializers.ImageField(required=False,allow_null=False)
    remover_avatar=serializers.BooleanField(write_only=True,required=False,default=False)
    cpf=serializers.CharField(required=False,allow_blank=True,allow_null=True,max_length=14)
    linhas=serializers.IntegerField(min_value=1,max_value=200,required=False)
    class Meta:
        model=Usuario
        fields=('id','username','first_name','last_name','email','cpf','fone','linhas','avatar','remover_avatar','date_joined','last_login','email_password')
        read_only_fields=('id','username','date_joined','last_login')
    def validate_avatar(self,value):
        if value.size>5*1024*1024:raise serializers.ValidationError('A imagem deve ter até 5 MB.')
        extension={'PNG':'png','JPEG':'jpg','WEBP':'webp'}.get(value.image.format)
        if not extension:raise serializers.ValidationError('Use PNG, JPEG ou WebP.')
        value.name=uuid.uuid4().hex+'.'+extension;return value
    def validate_cpf(self,value):
        if not value:return None
        digits=re.sub(r'\D','',value)
        if len(digits)!=11 or len(set(digits))==1 or not validar_cpf(digits):raise serializers.ValidationError('CPF inválido.')
        if Usuario.objects.filter(cpf=digits).exclude(pk=self.instance.pk).exists():raise serializers.ValidationError('Este CPF já está cadastrado.')
        return digits
    def validate_fone(self,value):
        if not value:return None
        if not re.fullmatch(r'[+\d() .-]+',value) or not 8<=len(re.sub(r'\D','',value))<=15:raise serializers.ValidationError('Telefone inválido.')
        return value
    def validate_email(self,value):
        if Usuario.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():raise serializers.ValidationError('Este e-mail já está cadastrado.')
        return Usuario.objects.normalize_email(value)
    def validate(self,attrs):
        if 'email' in attrs and attrs['email'].casefold()!=self.instance.email.casefold():
            if not check_password(attrs.get('email_password',''),self.instance.password):
                raise serializers.ValidationError({'email_password':'Confirme a senha atual para alterar o e-mail.'})
        return attrs
    def update(self,instance,validated_data):
        validated_data.pop('email_password',None)
        remove=validated_data.pop('remover_avatar',False)
        if remove and validated_data.get('avatar'):raise serializers.ValidationError({'avatar':'Escolha enviar ou remover a imagem.'})
        if remove:validated_data['avatar']=''
        return super().update(instance,validated_data)


class NovaSenhaSerializer(serializers.Serializer):
    new_password=serializers.CharField(write_only=True,max_length=256,trim_whitespace=False)
    conf_password=serializers.CharField(write_only=True,max_length=256,trim_whitespace=False)
    def validate(self,attrs):
        if attrs['new_password']!=attrs['conf_password']:raise serializers.ValidationError({'conf_password':'As senhas não conferem.'})
        return attrs


class TrocaSenhaSerializer(NovaSenhaSerializer):
    current_password=serializers.CharField(write_only=True,max_length=256,trim_whitespace=False)


class RecuperacaoSolicitarSerializer(serializers.Serializer):
    username=serializers.CharField(max_length=15)
    email=serializers.EmailField(max_length=255)


class RecuperacaoConfirmarSerializer(NovaSenhaSerializer):
    token=serializers.CharField(write_only=True,min_length=40,max_length=128,trim_whitespace=False)


class CadastroUsuarioSerializer(serializers.ModelSerializer):
    """Cadastro comum: empresas e permissões sempre limitadas pelo responsável."""
    password = serializers.CharField(write_only=True, max_length=256, trim_whitespace=False)
    conf_password = serializers.CharField(write_only=True, max_length=256, trim_whitespace=False)
    empresas = serializers.PrimaryKeyRelatedField(queryset=Empresa.objects.none(), many=True, allow_empty=False)
    permissoes = serializers.PrimaryKeyRelatedField(source='user_permissions', queryset=Permission.objects.none(), many=True, required=False)
    empresas_nomes = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'password', 'conf_password', 'empresas', 'empresas_nomes', 'permissoes', 'is_active', 'date_joined', 'uf')
        read_only_fields = ('id', 'empresas_nomes', 'is_active', 'date_joined', 'uf')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request:
            from .access import permissoes_delegaveis
            self.fields['empresas'].child_relation.queryset = request.user.empresas.all()
            self.fields['permissoes'].child_relation.queryset = permissoes_delegaveis(request.user)

    def get_empresas_nomes(self, obj):
        return [{'id': company.pk, 'razao': company.razao} for company in sorted(obj.empresas.all(), key=lambda company: (company.razao, company.pk))]

    def validate_username(self, value):
        if Usuario.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Nome de usuário indisponível.')
        return value

    def validate_email(self, value):
        if Usuario.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('E-mail indisponível.')
        return Usuario.objects.normalize_email(value)

    def validate(self, attrs):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        writable = {'username', 'first_name', 'last_name', 'email', 'password', 'conf_password', 'empresas', 'permissoes'}
        if set(self.initial_data) - writable:
            raise serializers.ValidationError('Foram enviados campos não permitidos para este cadastro.')
        if attrs['password'] != attrs.pop('conf_password'):
            raise serializers.ValidationError({'conf_password': 'As senhas não conferem.'})
        candidate = Usuario(**{key: attrs[key] for key in ('username', 'first_name', 'last_name', 'email') if key in attrs})
        try:
            validate_password(attrs['password'], candidate)
        except ValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return attrs

    def create(self, validated_data):
        companies = validated_data.pop('empresas')
        permissions = validated_data.pop('user_permissions', [])
        user = Usuario.objects.create_user(**validated_data, uf_id=self.context['request'].user.uf_id)
        user.empresas.set(companies)
        user.user_permissions.set(permissions)
        return user
