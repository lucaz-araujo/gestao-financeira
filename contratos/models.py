# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from auditlog.registry import auditlog
from django.db import models
from django.core.exceptions import ValidationError
from produtos.models import Produto


class Contrato(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    cliente = models.ForeignKey('clientes.Cliente',
                                related_name='Contrato',
                                on_delete=models.PROTECT)
    numero = models.CharField('Número', max_length=20, null=True)
    dia_nota = models.IntegerField('Dia da nota', null=True)
    dt_data_contrato = models.DateField('Data do contrato', null=True)
    dt_data_final = models.DateField('Data final', null=True)
    exercicio = models.IntegerField('Exercício', default=2017, null=True)
    objeto = models.TextField('Objeto', null=True)
    observacoes = models.TextField('Observações', null=True)
    valor_bruto = models.DecimalField('Valor da Nota',max_digits=10, decimal_places=2, null=True)
    perc_iss = models.DecimalField('% ISSQN', max_digits=10, decimal_places=2, null=True)
    perc_irpj = models.DecimalField('% IRPJ', max_digits=10, decimal_places=2, null=True)
    valor_iss = models.DecimalField('Valor ISS',max_digits=10,decimal_places=2,null=True)
    valor_irpj = models.DecimalField('Valor IRPJ', max_digits=10, decimal_places=2, null=True)
    valor_liquido = models.DecimalField('Valor líquido', max_digits=10, decimal_places=2, null=True)
    ativo = models.BooleanField(u'Está ativo', default=True)
    emitirnota = models.BooleanField(u'Emitir nota ?', default=True)
    prestacao_municipio = models.BooleanField(u'Prestação de serviços no município ?', default=False)

    def __str__(self):
        return f'{self.numero} - {self.cliente.instituicao}'

    def clean(self):
        super().clean()
        errors = {}
        if self.dt_data_contrato and self.dt_data_final and self.dt_data_contrato > self.dt_data_final:
            errors['dt_data_final'] = 'A data final deve ser igual ou posterior à inicial.'
        if self.dia_nota is not None and not 1 <= self.dia_nota <= 31:
            errors['dia_nota'] = 'Informe um dia entre 1 e 31.'
        if self.exercicio is not None and not 1 <= self.exercicio <= 9999:
            errors['exercicio'] = 'Informe um exercício válido.'
        for field in ('valor_bruto', 'valor_iss', 'valor_irpj', 'valor_liquido', 'perc_iss', 'perc_irpj'):
            value = getattr(self, field)
            if value is not None and (value < 0 or (field.startswith('perc_') and value > 100)):
                errors[field] = 'Informe um valor não negativo e percentuais de até 100%.'
        if self.cliente_id and self.empresa_id and self.cliente.empresa_id != self.empresa_id:
            errors['cliente'] = 'O cliente deve pertencer à empresa do contrato.'
        if errors:
            raise ValidationError(errors)

    @property
    def tem_nota(self):
        return self.ContNotas.all().count() > 0

    @property
    def produtos(self):
        retorno = ''
        if self.produtosCont:
            if self.produtosCont.all().count() > 0:
                for r in self.produtosCont.all():
                    if retorno == '':
                        retorno += f'{r.produtos.sigla}'
                    else:
                        retorno += f' - {r.produtos.sigla}'
        return retorno

    class Meta:
        verbose_name_plural = 'Contratos'


auditlog.register(Contrato)


class ContratoProduto(models.Model):
    contrato = models.ForeignKey(Contrato,
                                 related_name='produtosCont',
                                 null=False,
                                 on_delete=models.PROTECT)
    produtos = models.ForeignKey(Produto,
                                 null=False,
                                 on_delete=models.PROTECT)
    valor = models.DecimalField('Valor', max_digits=12, decimal_places=5, null=True)

    def __str__(self):
        return f'{self.contrato.cliente.instituicao} - {self.produtos.descricao}'

    class Meta:
        verbose_name_plural = 'ContratosProduto'


auditlog.register(ContratoProduto)


class ContratoRenovacao(models.Model):
    contrato = models.ForeignKey(Contrato,
                                 related_name='renovacao',
                                 on_delete=models.PROTECT)
    dt_data_inicio = models.DateField('Data de Inicio')
    dt_data_final = models.DateField('Data final')

    def __str__(self):
        return f'{self.contrato} - {self.dt_data_inicio}'

    class Meta:
        verbose_name_plural = 'ContratosRenovacao'


auditlog.register(ContratoRenovacao)
