# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models
from django.core.exceptions import ValidationError

TP_PRODUTO = (
    ('P', 'Produto'),
    ('S', 'Serviço')
)


class Produto(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    descricao = models.CharField('Descrição', max_length=60, null=False)
    tipo_produto = models.CharField('Tipo de Produto', choices=TP_PRODUTO, max_length=1, default='P', null=False)
    valor = models.DecimalField('Valor', max_digits=10, decimal_places=2, null=True)
    sigla = models.CharField(max_length=5, null=True, blank=False)

    def __str__(self):
        return f'{self.descricao}'

    def clean(self):
        super().clean()
        errors = {}
        if not self.descricao or not self.descricao.strip():
            errors['descricao'] = 'Informe a descrição.'
        if not self.sigla or not self.sigla.strip():
            errors['sigla'] = 'Informe a sigla.'
        if self.valor is None:
            errors['valor'] = 'Informe o valor.'
        elif self.valor < 0:
            errors['valor'] = 'O valor não pode ser negativo.'
        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name_plural = 'Produtos'
