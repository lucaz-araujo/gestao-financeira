# -*- coding: utf-8 -*-
from django.db import models
from django.core.exceptions import ValidationError

TIPO_CONTA = (
    ('R','Receita'),
    ('D','Despesa'),
    )

TIPO_MOVIMENTO = (
    ('C','Crédito'),
    ('D','Despesa'),
    )


class PlanoContas(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    conta = models.CharField(max_length=15)
    descricao = models.CharField(max_length=100)
    tipo = models.CharField(choices=TIPO_CONTA, max_length=1, null=True)
    codigo = models.CharField(max_length=5, null=True)

    def __str__(self):
        return f'{self.conta}-{self.descricao}'

    class Meta:
        ordering = ['conta']
        verbose_name = 'PlanoConta'
        verbose_name_plural = 'PlanoContas'


class CentroCusto(models.Model):
    def clean(self):
        if self.conta_id and self.conta.empresa_id != self.empresa_id:
            raise ValidationError({'conta': 'O plano deve pertencer à empresa do centro de custo.'})

    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    codigo = models.CharField('Codigo', max_length=3)
    descricao = models.CharField('Descrição',max_length=60)
    conta = models.ForeignKey(PlanoContas,
                              related_name='centrocusto',
                              null=True,
                              blank=True,
                              on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

    class Meta:
        ordering = ['descricao']
        verbose_name_plural = 'CentroCustos'


class TipoDespesa(models.Model):
    codigo = models.CharField('Código', max_length=3)
    descricao = models.CharField('Descrição', max_length=60)
    conta = models.ForeignKey(PlanoContas,
                              related_name='tipodespesa',
                              null=True,
                              blank=True,
                              on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.codigo} - {self.descricao}'

    class Meta:
        ordering = ['descricao']
        verbose_name_plural = 'TipoDespesas'


class Historico(models.Model):
    descricao = models.CharField('Descrição',max_length=100)

    def __str__(self):
        return f'{self.descricao}'

    class Meta:
        ordering = ['descricao']
        verbose_name_plural = 'Historicos'


class Lancamentos(models.Model):
    def clean(self):
        errors = {}
        if not self.conta_origem_id or not self.conta_destino_id:
            errors['conta_origem'] = 'Informe as duas contas.'
        elif not self.conta_origem.empresa_id or self.conta_origem.empresa_id != self.conta_destino.empresa_id:
            errors['conta_destino'] = 'As contas devem pertencer à mesma empresa.'
        elif self.conta_origem_id == self.conta_destino_id:
            errors['conta_destino'] = 'Escolha contas distintas.'
        if self.valor is None or self.valor <= 0:
            errors['valor'] = 'Informe um valor positivo.'
        if errors:
            raise ValidationError(errors)

    dt_data = models.DateTimeField(null=True)
    tipo = models.CharField(max_length=1, choices=TIPO_MOVIMENTO, null=True)
    conta_origem = models.ForeignKey(PlanoContas,
                                     related_name='lancamentoOrigem',
                                     null=True,
                                     on_delete=models.PROTECT)
    conta_destino = models.ForeignKey(PlanoContas,
                                      related_name='lancamentoDestino',
                                      null=True,
                                      on_delete=models.PROTECT)
    valor = models.DecimalField(max_digits=10,decimal_places=2,default=0,null=True)
    descricao = models.CharField('Descrição', max_length=60, null=True)

    def __str__(self):
        return f'{self.conta_origem.conta} => {self.conta_destino.conta} - {self.valor}'

    class Meta:
        ordering = ['dt_data']
        verbose_name_plural = 'Lancamentos'
