# -*- coding: utf-8 -*-
from django.db import models
from django.db.models import Sum

from clientes.models import Municipio, Uf

STATUS_COLICITACAO = (
    ('AB', 'ABERTA'),
    ('PE', 'PESQUISA ORÇAMENTO'),
    ('AU', 'AUTORIZADA'),
    ('FI', 'FINALIZADA'),
    ('CA', 'CANCELADA'),
)

FORMA_PAG = (
    ('DIN', 'Dinheiro'),
    ('CHE', 'Cheque'),
    ('CAR', 'Cartão'),
)


class Fornecedor(models.Model):
    def clean(self):
        from .validation import fornecedor_limpo
        fornecedor_limpo(self)

    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    instituicao = models.CharField('Instituição', max_length=60, unique=True)
    cnpj = models.CharField('C.N.P.J.', max_length=20, null=True, blank=True)
    cgf = models.CharField('C.G.F.', max_length=20, null=True, blank=True)
    cpf = models.CharField('C.P.F.', max_length=20, null=True, blank=True)
    endereco = models.CharField('Endereço', max_length=60)
    numero = models.CharField('Número', max_length=10)
    bairro = models.CharField('bairro', max_length=60)

    cidade = models.ForeignKey(Municipio,
                               null=True,
                               on_delete=models.PROTECT)
    uf = models.ForeignKey(Uf,
                           null=True,
                           on_delete=models.PROTECT)

    banco = models.ForeignKey('conta.Banco',
                              related_name='banco',
                              null=True,
                              blank=True,
                              on_delete=models.PROTECT)
    agencia = models.CharField(max_length=8, null=True, blank=True)
    dvagencia = models.CharField(max_length=1, null=True, blank=True)
    conta = models.CharField(max_length=10, null=True, blank=True)
    dvconta = models.CharField(max_length=1, null=True, blank=True)

    cep = models.CharField('C.E.P.', max_length=15)
    site = models.CharField('Site', max_length=100, null=True)
    resp_nome = models.CharField('Nome do responsável', max_length=60, null=True)
    resp_cargo = models.CharField('Cargo', max_length=60, null=True)
    resp_cpf = models.CharField('C.P.F.', max_length=20, null=True)
    resp_telefone = models.CharField('Telefone', max_length=20, null=True)
    resp_email = models.CharField('email', max_length=100, null=True)
    ativo = models.BooleanField('Ativo', default=True)

    def __str__(self):
        return f'{self.instituicao}'

    class Meta:
        ordering = ['instituicao']
        verbose_name_plural = 'Forncedores'


class Unidade(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    descricao = models.CharField(max_length=30)
    sigla = models.CharField(max_length=3, null=True)

    def __str__(self):
        return f'{self.descricao}'

    class Meta:
        ordering = ['descricao']
        verbose_name_plural = 'Unidades'


class Itens(models.Model):
    def clean(self):
        from .validation import item_limpo
        item_limpo(self)

    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    descricao = models.CharField(max_length=30)
    unidade = models.ForeignKey(Unidade,
                                on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.descricao}'

    class Meta:
        ordering = ['descricao']
        verbose_name_plural = 'Unidades'


class Solicitacao(models.Model):
    def clean(self):
        from .validation import solicitacao_limpa
        solicitacao_limpa(self)

    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    descricao = models.CharField('Descrição', max_length=100)
    user_solicitante = models.ForeignKey('usuario.Usuario',
                                         related_name='solicitante',
                                         on_delete=models.PROTECT)
    dt_solicitacao = models.DateField('Data de Solicitação')
    dt_autorizacao = models.DateField('Data de Autorização', null=True)
    user_autorizacao = models.ForeignKey('usuario.Usuario',
                                         related_name='autorizante',
                                         null=True,
                                         on_delete=models.PROTECT)
    status = models.CharField('Status', max_length=2, choices=STATUS_COLICITACAO, default='AB')
    centro_custo = models.ForeignKey('contabil.CentroCusto',
                                     null=True,
                                     on_delete=models.PROTECT)
    tipo_despesa = models.ForeignKey('contabil.TipoDespesa',
                                     null=True,
                                     on_delete=models.PROTECT)
    total = models.DecimalField('Valor Total', max_digits=10, decimal_places=3, null=True)

    def __str__(self):
        return f'{self.descricao}'

    def atuTotal(self):
        from decimal import Decimal
        self.total = self.solicitacaoitem_set.aggregate(valor=Sum('valor_total'))['valor'] or Decimal('0')
        self.save(update_fields=['total'])

    class Meta:
        ordering = ['dt_solicitacao']
        verbose_name_plural = 'Solicitacaes'
        permissions = (('autorizar_solicitacao', 'Pode autorizar solicitações de compras'),
                       ('finalizar_solicitacao', 'Pode finalizar solicitações de compras'))


class Orcamento(models.Model):
    def clean(self):
        from .validation import orcamento_limpo
        orcamento_limpo(self)

    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    fornecedor = models.ForeignKey(Fornecedor,
                                   on_delete=models.PROTECT)
    solicitacao = models.ForeignKey(Solicitacao,
                                    related_name='orcamentos_list',
                                    on_delete=models.PROTECT)
    dt_orcamento = models.DateField('Data do orçamento')
    nr_documento = models.CharField('Número de documento', max_length=15, null=True)
    forma_pag = models.CharField(max_length=3, null=True, choices=FORMA_PAG)
    qtd_parcelas = models.IntegerField(null=False, default=0)

    def __str__(self):
        return f'{self.fornecedor}'

    class Meta:
        ordering = ['dt_orcamento']
        verbose_name_plural = 'Orcamentos'


class OrcamentoItens(models.Model):
    def clean(self):
        from .validation import linha_limpa
        linha_limpa(self)

    orcamento = models.ForeignKey(Orcamento,
                                  related_name='orcamentoitens',
                                  on_delete=models.PROTECT)
    item = models.ForeignKey(Itens,
                             on_delete=models.PROTECT)
    quantidade = models.DecimalField('Quantidade', max_digits=10, decimal_places=3)
    valor = models.DecimalField('Valor Unitário', max_digits=10, decimal_places=3)
    valor_total = models.DecimalField('Valor Total', max_digits=10, decimal_places=3)
    menor_preco = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.orcamento}'

    class Meta:
        verbose_name_plural = 'OrcamentosItens'


class SolicitacaoItem(models.Model):
    def clean(self):
        from .validation import linha_limpa
        linha_limpa(self)

    solicitacao = models.ForeignKey(Solicitacao,
                                    on_delete=models.PROTECT)
    item = models.ForeignKey(Itens,
                             on_delete=models.PROTECT)
    quantidade = models.DecimalField('Quantidade', max_digits=10, decimal_places=3)
    valor = models.DecimalField('Valor Unitário', max_digits=10, decimal_places=3)
    valor_total = models.DecimalField('Valor Total', max_digits=10, decimal_places=3)
    orcamento = models.ForeignKey(OrcamentoItens,
                                  related_name='ItensOrcamento',
                                  null=True,
                                  on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.item}'

    class Meta:
        verbose_name_plural = 'SolicitacaoItens'
