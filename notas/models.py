# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from auditlog.registry import auditlog
from django.db import models
from clientes.models import Municipio, Uf
from financeiro.models import DocReceita
from clientes.models import Cliente
from datetime import datetime, date, timedelta
import uuid
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

CHOICE_COMPETENCIA = (
    (1, 'Janeiro'),
    (2, 'Fevereiro'),
    (3, 'Março'),
    (4, 'Abril'),
    (5, 'Maio'),
    (6, 'Junho'),
    (7, 'Julho'),
    (8, 'Agosto'),
    (9, 'Setembro'),
    (10, 'Outubro'),
    (11, 'Novembro'),
    (12, 'Dezembro'),
)

def exercicio_atual():
    return timezone.localdate().year



# Create your models here.
class Nota(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    contrato = models.ForeignKey('contratos.Contrato',
                                 null=False,
                                 related_name='ContNotas',
                                 on_delete=models.PROTECT)
    numero = models.CharField('Número da Nota', max_length=15, null=True)
    dt_data_emissao = models.DateTimeField('Data de Emissão', null=False)
    competencia = models.IntegerField(choices=CHOICE_COMPETENCIA, null=False)
    exercicio = models.IntegerField(default=exercicio_atual, validators=[MinValueValidator(1), MaxValueValidator(9999)])
    valor_bruto = models.DecimalField('Valor bruto', max_digits=10, decimal_places=2, null=True)
    dt_data_vencimento = models.DateTimeField('Data de Vencimento', null=True, blank=True)
    imposto = models.DecimalField('Imposto', max_digits=10, decimal_places=2, null=True, blank=True)
    aliq_imposto = models.DecimalField('Aliq. Imposto', max_digits=10, decimal_places=2, null=True, blank=True)
    valor_liquido = models.DecimalField('Valor', max_digits=10, decimal_places=2, null=True)
    dt_data_pagamento = models.DateField('Data de Pagamento', null=True, blank=True)
    ja_enviou = models.BooleanField('Já enviou nota', default=False, blank=True)
    ja_enviou_NFSE = models.BooleanField('Já enviou NFSE', default=False, blank=True)
    dt_data_envio = models.DateField('Data de envio', null=True, blank=True)
    arquivo_pdf = models.FileField('Arquivo pdf', upload_to='notas/', null=True, blank=True)
    texto_nota = models.TextField('Texto Nota', null=True)

    protocolo_envio = models.CharField('Protocolo Envio', max_length=400, null=True, blank=True)
    dt_data_envio_sefaz = models.DateTimeField('Data de Envio', null=True, blank=True)
    protocolo_recebimento = models.CharField('Protocolo Recebimento', max_length=400, null=True, blank=True)
    dt_data_autorizacao = models.DateTimeField('Data de Autorização', null=True, blank=True)
    numero_lote = models.IntegerField(null=True, blank=True)
    numero_rps = models.IntegerField(null=True, blank=True)

    prot_envio_can = models.CharField('Protocolo Cancelamento', max_length=20, null=True, blank=True)
    dt_data_envio_can = models.DateTimeField('Data Cancelamento', null=True, blank=True)
    decimo_terceiro = models.BooleanField(default=False, blank=True)

    cidade = models.ForeignKey(Municipio,
                               null=True,
                               blank=True,
                               on_delete=models.PROTECT)
    uf = models.ForeignKey(Uf,
                           null=True,
                           blank=True,
                           on_delete=models.PROTECT)

    coigo_servico = models.CharField(max_length=5, null=True, blank=True, default='104')
    codigo_cnae = models.CharField(max_length=8, null=True, blank=True, default='6202300')
    codigo_tributacao_municipio = models.CharField(max_length=15, null=True, blank=True, default='620230000')
    descr_tributacao_municipio = models.CharField(max_length=80, null=True, blank=True,
                                                  default='Desenvolvimento e licenciamento de programas de computador '
                                                          'customizáveis')

    cancelada_em = models.DateTimeField(null=True, blank=True, editable=False)

    def clean(self):
        super().clean()
        errors = {}
        if not 1 <= self.competencia <= 12:
            errors['competencia'] = 'Informe uma competência entre 1 e 12.'
        if not 1 <= self.exercicio <= 9999:
            errors['exercicio'] = 'Informe um exercício válido.'
        for field in ('valor_bruto', 'imposto', 'valor_liquido', 'aliq_imposto'):
            value = getattr(self, field)
            if value is not None and (value < 0 or (field == 'aliq_imposto' and value > 100)):
                errors[field] = 'Informe um valor não negativo e alíquota até 100%.'
        if self.empresa_id and self.contrato_id and (self.contrato.empresa_id != self.empresa_id or self.contrato.cliente.empresa_id != self.empresa_id):
            errors['contrato'] = 'Contrato e cliente devem pertencer à empresa da nota.'
        if self.cidade_id and (not self.uf_id or self.cidade.uf_id != self.uf_id):
            errors['cidade'] = 'O município deve pertencer à UF informada.'
        if errors:
            raise ValidationError(errors)

    @property
    def estado_fiscal(self):
        if self.cancelada_em:
            return 'cancelada'
        operations = list(self.operacoes.all())
        if any(op.estado == 'incerta' for op in operations):
            return 'incerta'
        if any(op.estado == 'executando' for op in operations):
            return 'processando'
        if self.protocolo_recebimento:
            return 'autorizada'
        if self.protocolo_envio or self.ja_enviou_NFSE:
            return 'enviada'
        if (self.numero_rps is not None or self.numero_lote is not None) and not any(op.acao == 'emitir' for op in operations):
            return 'incerta'
        return 'rascunho'

    def ja_pago(self):
        return self.docreceitas.filter(recebimento__isnull=False).exists()

    def get_competencia_min_display(self):
        return self.get_competencia_display()[:3]

    @property
    def ja_tem_financeiro(self):
        return self.docreceitas.all().count() > 0

    def gerarfinanceiro(self, usuario):
        from .services import gerar_receita
        gerar_receita(self.pk, usuario)
        return True

    def __str__(self):
        return f'{self.contrato}'

    class Meta:
        verbose_name_plural = 'Notas'


auditlog.register(Nota)


class OperacaoFiscal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nota = models.ForeignKey(Nota, related_name='operacoes', on_delete=models.PROTECT)
    usuario = models.ForeignKey('usuario.Usuario', on_delete=models.PROTECT)
    acao = models.CharField(max_length=20, choices=[(x, x) for x in ('emitir', 'consultar', 'consultar_lote', 'cancelar', 'email', 'email_cliente')])
    chave = models.UUIDField()
    estado = models.CharField(max_length=12, default='executando', choices=[(x, x) for x in ('executando', 'concluida', 'falha', 'incerta')])
    resultado = models.JSONField(default=dict)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criada_em']
        constraints = [models.UniqueConstraint(fields=['nota', 'acao', 'chave'], name='nota_operacao_chave_unica')]
        indexes = [models.Index(fields=['nota', 'estado'], name='nota_operacao_estado_idx')]
