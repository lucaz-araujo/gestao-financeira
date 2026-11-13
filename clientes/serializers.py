"""Contrato JSON do app clientes. Validações de entrada permanecem no servidor."""
from copy import copy
import re

from django.core.exceptions import ValidationError as ModelValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import Cliente, Parceiro, Uf, Municipio, MunicipioBr, Liberacao, LiberacaoDatas
from .validador import validar_cnpj, validar_cpf


class UfSerializer(serializers.ModelSerializer):
    class Meta:
        model = Uf
        fields = ('id', 'sigla', 'descricao', 'codgio_ibge')


class MunicipioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Municipio
        fields = ('id', 'uf', 'codigo_ibge', 'descricao')


class MunicipioBrSerializer(serializers.ModelSerializer):
    class Meta:
        model = MunicipioBr
        fields = ('id', 'cdmunic', 'ufmuni', 'cidade', 'cdtrib', 'ttvere2009')


class CadastroSerializer(serializers.ModelSerializer):
    uf_nome = serializers.CharField(source='uf.sigla', read_only=True, default=None)
    cidade_nome = serializers.CharField(source='cidade.descricao', read_only=True, default=None)

    def validate_cnpj(self, value):
        if value and not validar_cnpj(value):
            raise serializers.ValidationError('CNPJ inválido.')
        if value and len(set(re.sub(r'\D', '', value))) == 1:
            raise serializers.ValidationError('CNPJ inválido.')
        return value

    def validate_resp_cpf(self, value):
        if value and (not validar_cpf(value) or len(set(re.sub(r'\D', '', value))) == 1):
            raise serializers.ValidationError('CPF do responsável inválido.')
        return value

    def validate(self, attrs):
        cidade = attrs.get('cidade', getattr(self.instance, 'cidade', None))
        uf = attrs.get('uf', getattr(self.instance, 'uf', None))
        if cidade and (not uf or cidade.uf_id != uf.pk):
            raise serializers.ValidationError({'cidade': 'O município deve pertencer à UF informada.'})
        request = self.context.get('request')
        if request and request.user.uf_id and (not uf or uf.pk != request.user.uf_id):
            raise serializers.ValidationError({'uf': 'UF fora do seu escopo de acesso.'})
        return attrs


class ParceiroSerializer(CadastroSerializer):
    class Meta:
        model = Parceiro
        fields = ('id', 'empresa', 'uf_nome', 'cidade_nome', 'tipo_pessoa', 'instituicao', 'cnpj', 'gcf',
                  'endereco', 'numero', 'bairro', 'cidade', 'uf', 'cep', 'site',
                  'resp_nome', 'resp_cargo', 'resp_cpf', 'dt_resp_nascimento',
                  'resp_telefone', 'resp_email', 'excecao', 'libera_clientes', 'dt_data_limite')
        read_only_fields = ('id', 'empresa')
        extra_kwargs = {
            'gcf': {'required': False, 'allow_blank': True},
            'cidade': {'required': True, 'allow_null': False},
            'uf': {'required': True, 'allow_null': False},
        }

    def validate_cnpj(self, value):
        value = super().validate_cnpj(value)
        qs = Parceiro.objects.filter(cnpj=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if value and qs.exists():
            raise serializers.ValidationError('Este CNPJ já está informado.')
        return value


class ClienteSerializer(CadastroSerializer):
    parceiro_nome = serializers.CharField(source='parceiro.instituicao', read_only=True, default=None)
    banco_nome = serializers.CharField(source='banco.nome', read_only=True, default=None)

    class Meta:
        model = Cliente
        fields = ('id', 'empresa', 'uf_nome', 'cidade_nome', 'parceiro_nome', 'banco_nome', 'parceiro', 'tipo_pessoa', 'instituicao', 'cnpj',
                  'gcf', 'endereco', 'numero', 'bairro', 'cidade', 'uf', 'cep', 'site',
                  'resp_nome', 'resp_cargo', 'resp_cpf', 'dt_resp_nascimento',
                  'resp_telefone', 'resp_email', 'codigolayout', 'codigoentidade',
                  'codigosim', 'codigoold', 'codigotcm', 'senhatcm', 'usertcm',
                  'banco', 'agencia', 'ativo', 'libera_tcm', 'libera_pagonline',
                  'libera_sistema', 'desativar', 'observacoes', 'numero_conta',
                  'libera_transparencia', 'libera_contracheque', 'gerar_notas')
        read_only_fields = ('id', 'empresa')
        extra_kwargs = {
            'senhatcm': {'write_only': True},
            **{field: {'required': True, 'allow_null': False, 'allow_blank': False}
               for field in ('cnpj', 'endereco', 'numero', 'bairro', 'cep')},
            'uf': {'required': True, 'allow_null': False},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        parceiros = self.context.get('parceiros', Parceiro.objects.none())
        self.fields['parceiro'].queryset = parceiros

    def validate(self, attrs):
        attrs = super().validate(attrs)
        codigo = attrs.get('codigoentidade', getattr(self.instance, 'codigoentidade', None))
        layout = attrs.get('codigolayout', getattr(self.instance, 'codigolayout', None))
        if codigo and (not codigo.isascii() or not codigo.isdigit() or len(codigo) > 2):
            raise serializers.ValidationError({'codigoentidade': 'Informe até dois dígitos.'})
        if layout and codigo:
            qs = Cliente.objects.filter(codigolayout=layout, codigoentidade=codigo)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({'codigolayout': 'Combinação Layout/entidade já cadastrada.'})
        return attrs


class ClienteRelacionadoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source='cliente.instituicao', read_only=True, default=None)
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True, default=None)

    """Restringe escolhas ao conjunto de clientes autorizado pela view."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].queryset = self.context.get('clientes', Cliente.objects.none())
        self.fields['cliente'].allow_null = False
        self.fields['cliente'].required = True


class LiberacaoSerializer(ClienteRelacionadoSerializer):
    competencia = serializers.CharField(max_length=2)
    exercicio = serializers.IntegerField(min_value=1, max_value=9999)

    class Meta:
        model = Liberacao
        fields = ('id', 'cliente', 'cliente_nome', 'usuario_nome', 'competencia', 'exercicio', 'produto',
                  'dt_liberacao', 'chave', 'codigo', 'codigo_layout', 'usuario')
        read_only_fields = ('id', 'produto', 'dt_liberacao', 'chave', 'codigo', 'codigo_layout', 'usuario')
        validators = []  # Campos derivados são validados após obter o cliente autorizado.

    def validate_competencia(self, value):
        if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 12:
            raise serializers.ValidationError('Informe um mês entre 1 e 12.')
        return value.zfill(2)

    def validate(self, attrs):
        candidate = copy(self.instance) if self.instance else Liberacao()
        for field, value in attrs.items():
            setattr(candidate, field, value)
        if candidate.cliente.desativar:
            raise serializers.ValidationError({'cliente': 'Cliente desativado.'})
        try:
            candidate.atualizar_chave()
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        qs = Liberacao.objects.filter(chave=candidate.chave)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({'competencia': 'Competência já liberada.'})
        return attrs

    def create(self, validated_data):
        obj = Liberacao(**validated_data, dt_liberacao=timezone.now())
        obj.atualizar_chave()
        obj.save()
        return obj


class LiberacaoDatasSerializer(ClienteRelacionadoSerializer):
    class Meta:
        model = LiberacaoDatas
        fields = ('id', 'cliente', 'cliente_nome', 'usuario_nome', 'usuario', 'dt_ate', 'dt_aparte', 'libera_tcm',
                  'libera_pagonline', 'libera_sistema', 'desativar',
                  'libera_transparencia', 'libera_contracheque', 'gerar_notas')
        read_only_fields = ('id', 'usuario')

    def validate(self, attrs):
        candidate = copy(self.instance) if self.instance else LiberacaoDatas()
        for field, value in attrs.items():
            setattr(candidate, field, value)
        try:
            candidate.clean()
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


class ClienteReportSerializer(ClienteSerializer):
    contratos = serializers.SerializerMethodField()

    class Meta(ClienteSerializer.Meta):
        fields = ClienteSerializer.Meta.fields + ('contratos',)

    def get_contratos(self, obj):
        # Empresas diferentes nunca entram no relatório, mesmo em vínculos legados inconsistentes.
        contratos = obj.Contrato.filter(empresa_id=obj.empresa_id, ativo=True).prefetch_related('produtosCont__produtos')
        return [{'id': c.pk, 'numero': c.numero, 'dt_data_contrato': c.dt_data_contrato,
                 'dt_data_final': c.dt_data_final, 'valor_bruto': str(c.valor_bruto) if c.valor_bruto is not None else None,
                 'produtos': [{'id': p.produtos_id, 'sigla': p.produtos.sigla,
                               'valor': str(p.valor) if p.valor is not None else None}
                              for p in c.produtosCont.all() if p.produtos.empresa_id == obj.empresa_id]}
                for c in contratos]




class BancoSerializer(serializers.ModelSerializer):
    descricao = serializers.SerializerMethodField()

    class Meta:
        from conta.models import Banco
        model = Banco
        fields = ('id', 'descricao')

    def get_descricao(self, obj):
        return f'{obj.codigo} - {obj.nome}'
