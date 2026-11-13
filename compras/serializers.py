from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Q
from rest_framework import serializers
from conta.serializers import CleanSerializer
from contabil.models import CentroCusto, TipoDespesa
from .models import Fornecedor, Unidade, Itens, Solicitacao, SolicitacaoItem, Orcamento, OrcamentoItens


def total_linha(quantity, price):
    value = (quantity * price).quantize(Decimal('.001'), rounding=ROUND_HALF_UP)
    if value > Decimal('9999999.999'):
        raise serializers.ValidationError({'valor':'O total da linha excede o limite permitido.'})
    return value


class FornecedorSerializer(CleanSerializer):
    cidade_nome = serializers.CharField(source='cidade.descricao',read_only=True,default=None)
    uf_sigla = serializers.CharField(source='uf.sigla',read_only=True,default=None)
    resp_email = serializers.EmailField(required=False,allow_blank=True,allow_null=True,max_length=100)
    class Meta:
        model = Fornecedor
        fields = ('id','empresa','instituicao','cnpj','cpf','cgf','endereco','numero','bairro','cidade','cidade_nome','uf','uf_sigla','cep','site','resp_nome','resp_cargo','resp_cpf','resp_telefone','resp_email','banco','agencia','dvagencia','conta','dvconta','ativo')
        read_only_fields = ('id','empresa')
        extra_kwargs = {name:{'required':False,'allow_null':True,'allow_blank':True} for name in ('site','resp_nome','resp_cargo','resp_cpf','resp_telefone')}


class UnidadeSerializer(CleanSerializer):
    class Meta:
        model = Unidade
        fields = ('id','empresa','descricao','sigla')
        read_only_fields = ('id','empresa')
        extra_kwargs = {'sigla':{'required':True,'allow_null':False,'allow_blank':False}}


class ItemSerializer(CleanSerializer):
    unidade_nome = serializers.CharField(source='unidade.sigla',read_only=True)
    class Meta:
        model = Itens
        fields = ('id','empresa','descricao','unidade','unidade_nome')
        read_only_fields = ('id','empresa')
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['unidade'].queryset = Unidade.objects.filter(empresa_id=self.context.get('empresa_id'))


class LinhaSerializer(serializers.ModelSerializer):
    quantidade = serializers.DecimalField(max_digits=10,decimal_places=3,min_value=Decimal('.001'))
    valor = serializers.DecimalField(max_digits=10,decimal_places=3,min_value=Decimal('0'))
    item_nome = serializers.CharField(source='item.descricao',read_only=True)
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['item'].queryset = Itens.objects.filter(empresa_id=self.context.get('empresa_id'),unidade__empresa_id=self.context.get('empresa_id'))
    def validate(self,attrs):
        total_linha(attrs['quantidade'],attrs['valor'])
        return attrs


class SolicitacaoLinhaSerializer(LinhaSerializer):
    class Meta:
        model = SolicitacaoItem
        fields = ('id','item','item_nome','quantidade','valor','valor_total','orcamento')
        read_only_fields = ('id','valor_total','orcamento')


class OrcamentoLinhaSerializer(LinhaSerializer):
    class Meta:
        model = OrcamentoItens
        fields = ('id','item','item_nome','quantidade','valor','valor_total','menor_preco')
        read_only_fields = ('id','valor_total','menor_preco')


def validar_linhas(lines):
    if not 1 <= len(lines) <= 100: raise serializers.ValidationError({'linhas':'Informe de 1 a 100 itens.'})
    ids = [line['item'].pk for line in lines]
    if len(set(ids)) != len(ids): raise serializers.ValidationError({'linhas':'Cada item deve aparecer uma única vez.'})
    if sum(total_linha(line['quantidade'],line['valor']) for line in lines) > Decimal('9999999.999'):
        raise serializers.ValidationError({'linhas':'O total excede o limite permitido.'})


class SolicitacaoSerializer(CleanSerializer):
    linhas = SolicitacaoLinhaSerializer(many=True,source='solicitacaoitem_set')
    solicitante_nome = serializers.CharField(source='user_solicitante.username',read_only=True)
    autorizador_nome = serializers.CharField(source='user_autorizacao.username',read_only=True,default=None)
    class Meta:
        model = Solicitacao
        fields = ('id','empresa','descricao','user_solicitante','solicitante_nome','dt_solicitacao','dt_autorizacao','user_autorizacao','autorizador_nome','status','centro_custo','tipo_despesa','total','linhas')
        read_only_fields = ('id','empresa','user_solicitante','dt_autorizacao','user_autorizacao','status','total')
        extra_kwargs = {name:{'required':False,'allow_null':True} for name in ('centro_custo','tipo_despesa')}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        company = self.context.get('empresa_id')
        self.fields['linhas'].child.fields['item'].queryset = Itens.objects.filter(empresa_id=company,unidade__empresa_id=company)
        self.fields['centro_custo'].queryset = CentroCusto.objects.filter(empresa_id=company)
        self.fields['tipo_despesa'].queryset = TipoDespesa.objects.filter(Q(conta__isnull=True)|Q(conta__empresa_id=company))
    def validate(self,attrs):
        lines = attrs.get('solicitacaoitem_set')
        if lines is not None: validar_linhas(lines)
        super().validate({k:v for k,v in attrs.items() if k!='solicitacaoitem_set'})
        return attrs
    def create(self,validated_data):
        lines = validated_data.pop('solicitacaoitem_set')
        obj = Solicitacao.objects.create(**validated_data)
        self.gravar_linhas(obj,lines)
        return obj
    def update(self,instance,validated_data):
        lines = validated_data.pop('solicitacaoitem_set',None)
        obj = super().update(instance,validated_data)
        if lines is not None:
            obj.solicitacaoitem_set.all().delete(); self.gravar_linhas(obj,lines)
        return obj
    def gravar_linhas(self,obj,lines):
        for line in lines:
            row = SolicitacaoItem(solicitacao=obj,**line,valor_total=total_linha(line['quantidade'],line['valor']))
            row.clean(); row.save()
        obj.atuTotal()


class OrcamentoSerializer(CleanSerializer):
    linhas = OrcamentoLinhaSerializer(many=True,source='orcamentoitens')
    fornecedor_nome = serializers.CharField(source='fornecedor.instituicao',read_only=True)
    total = serializers.SerializerMethodField()
    def get_total(self,obj): return str(sum(((line.valor_total or Decimal('0')) for line in obj.orcamentoitens.all()),Decimal('0')))
    class Meta:
        model = Orcamento
        fields = ('id','empresa','fornecedor','fornecedor_nome','solicitacao','dt_orcamento','nr_documento','forma_pag','qtd_parcelas','linhas','total')
        read_only_fields = ('id','empresa')
        extra_kwargs = {'qtd_parcelas':{'min_value':0,'max_value':120},'nr_documento':{'required':False,'allow_null':True,'allow_blank':True}}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        company = self.context.get('empresa_id')
        self.fields['linhas'].child.fields['item'].queryset = Itens.objects.filter(empresa_id=company,unidade__empresa_id=company)
        self.fields['fornecedor'].queryset = Fornecedor.objects.filter(empresa_id=company)
        self.fields['solicitacao'].queryset = self.context.get('solicitacoes',Solicitacao.objects.none())
    def validate(self,attrs):
        if self.instance and attrs.get('solicitacao',self.instance.solicitacao).pk != self.instance.solicitacao_id:
            raise serializers.ValidationError({'solicitacao':'Não é permitido trocar a solicitação do orçamento.'})
        lines = attrs.get('orcamentoitens')
        if lines is not None: validar_linhas(lines)
        super().validate({k:v for k,v in attrs.items() if k!='orcamentoitens'})
        return attrs
    def create(self,validated_data):
        lines = validated_data.pop('orcamentoitens')
        obj = Orcamento.objects.create(**validated_data); self.gravar_linhas(obj,lines); return obj
    def update(self,instance,validated_data):
        lines = validated_data.pop('orcamentoitens',None)
        obj = super().update(instance,validated_data)
        if lines is not None:
            obj.orcamentoitens.all().delete(); self.gravar_linhas(obj,lines)
        return obj
    def gravar_linhas(self,obj,lines):
        requested = {row.item_id:row for row in obj.solicitacao.solicitacaoitem_set.all()}
        for line in lines:
            request = requested.get(line['item'].pk)
            if not request or request.quantidade != line['quantidade']:
                raise serializers.ValidationError({'linhas':'Cote somente os itens e quantidades exatos da solicitação.'})
            row = OrcamentoItens(orcamento=obj,**line,valor_total=total_linha(line['quantidade'],line['valor']))
            row.clean(); row.save()
