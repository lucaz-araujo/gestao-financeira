# -*- coding: utf-8 -*-
from django.db import models
from django.utils import timezone
from auditlog.registry import auditlog
from compras.models import Fornecedor
from clientes.models import Cliente, Liberacao
import datetime
import hashlib
from django.conf import settings


SIT_DESPESAS = (
    ('A','ABERTA'),
    ('P','PAGA'),
    ('V','VENCIDA'),
    )

FPAG_DESPESAS = (
    ('D','DINHEIRO'),
    ('C','CHEQUE'),
    ('T','TRANSAÇÃO BANCÁRIA'),
    ('E','CARTÃO VISA'),
    )

SIT_RECEITA = (
    ('A','ABERTA'),
    ('R','RECEBIDA'),
    ('V','VENCIDA'),
    )


class DocDespesa(models.Model):
    def clean(self):
        from .validation import documento_limpo
        documento_limpo(self)

    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    fornecedor = models.ForeignKey(Fornecedor,
                                   on_delete=models.PROTECT)
    numero = models.CharField(max_length=30)
    descricao = models.CharField(max_length=500)
    dt_vencimento = models.DateField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True)
    dt_registro = models.DateField()
    user_registro = models.ForeignKey('usuario.Usuario',
                                      on_delete=models.PROTECT)
    situacao = models.CharField(choices=SIT_DESPESAS, max_length=1, default='A')

    tipo_despesa = models.ForeignKey('contabil.TipoDespesa',
                                     null=True,
                                     on_delete=models.PROTECT)
    centro_custo = models.ForeignKey('contabil.CentroCusto',
                                     null=True,
                                     on_delete=models.PROTECT)

    @property
    def registro_pagamento(self):
        if self.pagamentos.all().count() > 0:
            return '{}-{}-{}-{}-{} {}'.format(self.pagamentos.all()[0].dt_pagamento.strftime('%d/%m/%Y'),
                                              self.pagamentos.all()[0].get_forma_pagamento_display(),
                                              self.pagamentos.all()[0].valor,
                                              self.pagamentos.all()[0].conta.banco,
                                              self.pagamentos.all()[0].conta.descricao,
                                              self.pagamentos.all()[0].obs if self.pagamentos.all()[0].obs is not None else '')
        else:
            return ''

    @property
    def forma_pagamento(self):
        if self.pagamentos.all().count() > 0:
            return f'{self.pagamentos.all()[0].get_forma_pagamento_display()}'
        else:
            return ''

    def __str__(self):
        return f'{self.numero} - {self.descricao}- {self.valor}'

    class Meta:
        ordering = ['dt_vencimento']
        verbose_name_plural = 'DocDespesas'
        permissions = (
            ('view_doc_despesa', 'View Doc Despesa'),
        )


auditlog.register(DocDespesa)


class PagDespesa(models.Model):
    def clean(self):
        from .validation import baixa_limpa
        baixa_limpa(self)

    despesa = models.ForeignKey(DocDespesa,
                                related_name='pagamentos',
                                on_delete=models.PROTECT)
    conta = models.ForeignKey('conta.Conta',
                              related_name='contaPagamento',
                              null=True,
                              on_delete=models.PROTECT)
    forma_pagamento = models.CharField(max_length=1, choices=FPAG_DESPESAS, default='D')
    numero_cheque = models.CharField(max_length=10, null=True, blank=True)
    dt_pagamento = models.DateField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    dt_registro = models.DateField(auto_now=True)
    user_registro = models.ForeignKey('usuario.Usuario',
                                      on_delete=models.PROTECT)
    obs = models.CharField(max_length=200, default=' ', null=True, blank=True)

    def __str__(self):
        return f'{self.despesa.numero} - {self.valor}'

    class Meta:
        ordering = ['dt_pagamento']
        verbose_name_plural = 'PagDespesas'
        permissions = (
            ('view_pag_despesa', 'View Pag Despesa'),
        )


auditlog.register(PagDespesa)


class DocReceita(models.Model):
    def clean(self):
        from .validation import documento_limpo
        documento_limpo(self)

    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    numero = models.CharField(max_length=30)
    nota = models.ForeignKey('notas.Nota',
                             related_name='docreceitas',
                             on_delete=models.PROTECT)
    descricao = models.TextField()
    dt_vencimento = models.DateField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    valor_recebido = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True)
    dt_registro = models.DateField()
    user_registro = models.ForeignKey('usuario.Usuario',
                                      on_delete=models.PROTECT)
    situacao = models.CharField(choices=SIT_RECEITA, max_length=1, default='A')

    @property
    def registro_pagamento(self):
        if self.recebimento.all().count() > 0:
            return '{}-{}-{} {} {}'.format(self.recebimento.all()[0].dt_pagamento.strftime('%d/%m/%Y'),
                                        self.recebimento.all()[0].valor,
                                        self.recebimento.all()[0].conta.banco,
                                        self.recebimento.all()[0].conta.descricao,
                                        self.recebimento.all()[0].obs if self.recebimento.all()[0].obs is not None else '')
        else:
            return ''

    @property
    def doc_mensagem(self):
        return '''{}'''.format(self.descricao.replace('\r\n', ' '))

    def __str__(self):
        return f'{self.numero} - {self.valor}'

    class Meta:
        ordering = ['dt_vencimento']
        verbose_name_plural = 'DocReceitas'
        permissions = (
            ('view_doc_receita', 'View doc receita'),
        )


auditlog.register(DocReceita)


class RecReceita(models.Model):
    def clean(self):
        from .validation import baixa_limpa
        baixa_limpa(self)

    receita = models.ForeignKey(DocReceita,
                                related_name='recebimento',
                                on_delete=models.PROTECT)
    conta = models.ForeignKey('conta.Conta',
                              related_name='contaRecebimento',
                              null=True,
                              on_delete=models.PROTECT)
    dt_pagamento = models.DateField()
    valor = models.DecimalField(max_digits=10,decimal_places=2)
    dt_registro = models.DateField(auto_now=True)
    user_registro = models.ForeignKey('usuario.Usuario', on_delete=models.PROTECT)
    obs = models.CharField(max_length=200, default=' ', null=True, blank=True)

    def __str__(self):
        return f'{self.receita.numero} - {self.valor}'

    def liberames(self):
        try:
            c = Cliente.objects.get(pk=self.receita.cliente.id)
            try:
                l = Liberacao.objects.get(cliente=c,
                                          competencia=self.receita.nota.competencia,
                                          exercicio=self.receita.nota.exercicio)
            except Liberacao.DoesNotExist:
                vhash = bytes( str(c.id) +
                               str(c.codigolayout) +
                               str(self.receita.nota.competencia).zfill(2) +
                               str(c.codigoentidade) +
                               str(self.receita.nota.exercicio) +
                               str(self.user_registro.id) +
                               str(datetime.date.today()) +
                               settings.API_SECRET_KEY, 'ascii')
                l = Liberacao(cliente=c,
                              codigo_layout=c.codigolayout,
                              codigo=c.codigoentidade,
                              competencia=str(self.receita.nota.competencia).zfill(2),
                              exercicio=self.receita.nota.exercicio,
                              usuario=self.user_registro,
                              dt_liberacao=timezone.now(),
                              chave=hashlib.md5(vhash).hexdigest()
                              )
                l.save()
        except Cliente.DoesNotExist:
            pass

    class Meta:
        ordering = ['dt_pagamento']
        verbose_name_plural = 'RecReceitas'
        permissions = (
            ('view_rec_receita', 'View rec receita'),
        )


auditlog.register(RecReceita)


class FechamentoCaixa(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    data = models.DateField()
    hora = models.TimeField()
    user_fechamento = models.ForeignKey('usuario.Usuario', on_delete=models.PROTECT)
    receitas = models.DecimalField(max_digits=15, decimal_places=4, null=True, default=0)
    despesas = models.DecimalField(max_digits=15, decimal_places=4, null=True, default=0)
    saldo = models.DecimalField(max_digits=15, decimal_places=4)
    saldo_anterior = models.DecimalField(max_digits=15, decimal_places=4)
    conta = models.ForeignKey('conta.Conta',
                              related_name='contaFechamento',
                              null=True,
                              on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.data} - {self.saldo}'

    class Meta:
        ordering = ['data']
        verbose_name_plural = 'FechamentosCaixa'
        unique_together = ('conta', 'data',)
        permissions = (
            ('view_fechamento_caixa', 'View fechamento caixa'),
        )


auditlog.register(FechamentoCaixa)


class Configuracao(models.Model):
    descricao = models.CharField(max_length=30)
    liberaquantnotasabertas = models.IntegerField(default=1)
    liberaquantnotasvencidas = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.descricao}'

    class Meta:
        verbose_name_plural = 'Configuracao'
        permissions = (
            ('view_Configuracao', 'View Configuracao'),
        )


auditlog.register(Configuracao)


class Analise(models.Model):
    tipo_movimento = models.CharField(max_length=1)
    exercicio = models.IntegerField()
    centrocusto = models.CharField(max_length=40)
    tipodespesa = models.CharField(max_length=40)

    janp = models.DecimalField(max_digits=15, decimal_places=2)
    fevp = models.DecimalField(max_digits=15, decimal_places=2)
    marp = models.DecimalField(max_digits=15, decimal_places=2)
    abrp = models.DecimalField(max_digits=15, decimal_places=2)
    maip = models.DecimalField(max_digits=15, decimal_places=2)
    junp = models.DecimalField(max_digits=15, decimal_places=2)
    julp = models.DecimalField(max_digits=15, decimal_places=2)
    agop = models.DecimalField(max_digits=15, decimal_places=2)
    setp = models.DecimalField(max_digits=15, decimal_places=2)
    outp = models.DecimalField(max_digits=15, decimal_places=2)
    novp = models.DecimalField(max_digits=15, decimal_places=2)
    dezp = models.DecimalField(max_digits=15, decimal_places=2)

    janr = models.DecimalField(max_digits=15, decimal_places=2)
    fevr = models.DecimalField(max_digits=15, decimal_places=2)
    marr = models.DecimalField(max_digits=15, decimal_places=2)
    abrr = models.DecimalField(max_digits=15, decimal_places=2)
    mair = models.DecimalField(max_digits=15, decimal_places=2)
    junr = models.DecimalField(max_digits=15, decimal_places=2)
    julr = models.DecimalField(max_digits=15, decimal_places=2)
    agor = models.DecimalField(max_digits=15, decimal_places=2)
    setr = models.DecimalField(max_digits=15, decimal_places=2)
    outr = models.DecimalField(max_digits=15, decimal_places=2)
    novr = models.DecimalField(max_digits=15, decimal_places=2)
    dezr = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        db_table = 'fn_analise'
        managed = False


class OperacaoBaixa(models.Model):
    """Chave durável: repetir uma requisição nunca duplica nem recria uma baixa estornada."""
    chave = models.UUIDField(primary_key=True, editable=False)
    empresa = models.ForeignKey('empresa.Empresa', on_delete=models.PROTECT)
    usuario = models.ForeignKey('usuario.Usuario', on_delete=models.PROTECT)
    assinatura = models.CharField(max_length=64)
    recurso = models.CharField(max_length=20)
    registro = models.PositiveBigIntegerField()
    criada_em = models.DateTimeField(auto_now_add=True)
