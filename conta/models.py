# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from auditlog.registry import auditlog
from django.db import models
from contabil.models import PlanoContas
from usuario.models import Usuario
from django.core.exceptions import ValidationError

TIPO_DOCUMENTO=(
    ('TED','TED'),
    ('DOC','DOC'),
    ('CHE','CHEQUE'),
    ('TAR','TARIFA'),
    ('OUT','OUTROS'),
    ('DEP','DEPOSITO'),
    ('TRA','TRANSFERÊNCIA'),
)

TIPO_MOVIMENTO = (
    ('C','Crédito'),
    ('D','Débito'),
)


class Banco(models.Model):
    codigo = models.CharField('Codigo', max_length=8)
    nome = models.CharField('Nome', max_length=10)

    def __str__(self):
        return f'{self.codigo}-{self.nome}'

    class Meta:
        ordering = ['codigo']
        verbose_name_plural = 'Bancos'


auditlog.register(Banco)


class Conta(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    banco = models.ForeignKey(Banco,
                              on_delete=models.PROTECT)
    conta_contabil = models.ForeignKey(PlanoContas,
                                       related_name='conta_contabil',
                                       null=True,
                                       on_delete=models.PROTECT)
    agencia = models.CharField('Agència', max_length=10)
    dv_agencia = models.CharField('Dv Agência', max_length=1)
    numeroconta = models.CharField('Número Conta', max_length=12)
    dv_conta = models.CharField('Dv Conta', max_length=1, null=True)
    descricao = models.CharField('Descrição', max_length=30)

    def clean(self):
        super().clean()
        if self.conta_contabil_id and self.conta_contabil.empresa_id != self.empresa_id:
            raise ValidationError({'conta_contabil': 'O plano de contas deve pertencer à empresa selecionada.'})

    def __str__(self):
        return f'{self.banco} - {self.numeroconta} - {self.dv_conta} - {self.descricao}'

    class Meta:
        ordering = ['numeroconta']
        verbose_name_plural = 'Contas'


auditlog.register(Conta)


class Transferencia(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    conta_origem = models.ForeignKey(Conta, related_name='contaOrigem', on_delete=models.PROTECT)
    conta_destino = models.ForeignKey(Conta, related_name='contaDestino', on_delete=models.PROTECT)
    nr_documento = models.CharField(max_length=20, null=True)
    dt_movimento = models.DateField()
    valor = models.DecimalField(max_digits=15, decimal_places=3)
    usuario = models.ForeignKey(Usuario, null=True, on_delete=models.PROTECT)
    historico = models.CharField(max_length=260, null=True)

    def par_consistente(self, legs=None):
        legs = list(self.transferencia.all()) if legs is None else legs
        if len(legs) != 2 or {m.tipo_movimento for m in legs} != {'C', 'D'}:
            return False
        return all(m.empresa_id == self.empresa_id and m.valor == self.valor and m.dt_movimento == self.dt_movimento
                   and m.tipo_documento == 'TRA' and not m.receita_id and not m.despesa_id
                   and m.conta_id == (self.conta_origem_id if m.tipo_movimento == 'D' else self.conta_destino_id)
                   for m in legs)

    def clean(self):
        super().clean()
        errors = {}
        if self.conta_origem_id and self.conta_origem_id == self.conta_destino_id:
            errors['conta_destino'] = 'Escolha contas de origem e destino diferentes.'
        for name in ('conta_origem', 'conta_destino'):
            if getattr(self, name + '_id') and getattr(self, name).empresa_id != self.empresa_id:
                errors[name] = 'A conta deve pertencer à empresa selecionada.'
        if self.valor is not None and self.valor <= 0:
            errors['valor'] = 'Informe um valor positivo.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.conta_origem} - {self.conta_destino} - {self.valor}'

    class Meta:
        ordering = ['dt_movimento']
        verbose_name_plural = 'Transferencias'


auditlog.register(Transferencia)


class Movimento(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    conta = models.ForeignKey(Conta, on_delete=models.PROTECT)
    tipo_documento = models.CharField(choices=TIPO_DOCUMENTO, max_length=3, verbose_name='Tipo de Documento')
    nr_documento = models.CharField(max_length=20, null=True, verbose_name='Número do Documento')
    dt_movimento = models.DateField(verbose_name='Data de Movimento')
    tipo_movimento = models.CharField(choices=TIPO_MOVIMENTO, max_length=1, verbose_name='Tipo de Movimento')
    valor = models.DecimalField(max_digits=15, decimal_places=3)
    usuario = models.ForeignKey(Usuario, null=True, verbose_name='Usuário', on_delete=models.PROTECT)
    historico = models.CharField(max_length=560, null=True, verbose_name='Histórico')
    receita = models.ForeignKey('financeiro.RecReceita',
                                related_name='recreceita',
                                null=True,
                                blank=True,
                                on_delete=models.PROTECT)
    despesa = models.ForeignKey('financeiro.PagDespesa',
                                related_name='pagdespesa',
                                null=True,
                                blank=True,
                                on_delete=models.PROTECT)
    transferencia = models.ForeignKey(Transferencia,
                                      related_name='transferencia',
                                      null=True,
                                      blank=True,
                                      on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.conta} - {self.tipo_movimento} - {self.valor} - {self.dt_movimento}'

    def clean(self):
        super().clean()
        errors = {}
        if self.conta_id and self.empresa_id != self.conta.empresa_id:
            errors['conta'] = 'A conta deve pertencer à empresa do movimento.'
        if self.valor is not None and self.valor <= 0:
            errors['valor'] = 'Informe um valor positivo.'
        links = [self.receita_id, self.despesa_id, self.transferencia_id]
        if sum(x is not None for x in links) > 1:
            errors['vinculo'] = 'Um movimento deve possuir apenas um vínculo de origem.'
        if self.receita_id and (self.receita.receita.empresa_id != self.empresa_id or self.receita.conta_id != self.conta_id or self.tipo_movimento != 'C'):
            errors['receita'] = 'Recebimento incompatível com o movimento.'
        if self.despesa_id and (self.despesa.despesa.empresa_id != self.empresa_id or self.despesa.conta_id != self.conta_id or self.tipo_movimento != 'D'):
            errors['despesa'] = 'Pagamento incompatível com o movimento.'
        if self.transferencia_id and self.transferencia.empresa_id != self.empresa_id:
            errors['transferencia'] = 'A transferência deve pertencer à empresa do movimento.'
        if errors:
            raise ValidationError(errors)

    class Meta:
        ordering = ['dt_movimento']
        verbose_name_plural = 'Movimentos'


auditlog.register(Movimento)


def AddMovimento(obj, tipo):
    # Compatibilidade com o Financeiro legado, usando o vínculo do pagamento.
    from .services import sincronizar_pagamento
    return sincronizar_pagamento(obj, tipo)
