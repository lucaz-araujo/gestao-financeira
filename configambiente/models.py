# -*- coding: utf-8 -*-
from django.db import models
from .storage import PrivateCertificateStorage, certificate_name
from .fields import CertificatePasswordField


class Ambiente(models.Model):
    def clean(self):
        import math
        from django.core.exceptions import ValidationError
        errors = {}
        if not (self.descricao or '').strip(): errors['descricao'] = 'Informe uma descrição.'
        if self.aliquota_iss is not None and (not math.isfinite(self.aliquota_iss) or not 0 <= self.aliquota_iss <= 100):
            errors['aliquota_iss'] = 'Informe uma alíquota entre 0 e 100.'
        for field in ('numero_lote','numero_rps'):
            value = str(getattr(self,field) or '0')
            if not value.isascii() or not value.isdigit() or not 0 <= int(value) <= 2147483647:
                errors[field] = 'Sequência inválida: informe um inteiro não negativo dentro do limite suportado.'
        if errors: raise ValidationError(errors)

    descricao = models.CharField(u'Descrição',max_length=30,null=False)
    certificado = models.FileField(u'Certificado',null=False,upload_to=certificate_name,storage=PrivateCertificateStorage())
    senha = CertificatePasswordField(u'Senha',null=False)
    homologacao = models.BooleanField(u'Ambiente de Homologação',default=True)
    aliquota_iss = models.FloatField(u'Aliquota iss',max_length=5,null=True)
    numero_lote=models.CharField(u'Número Lote', max_length=15,null=True, default=0)
    numero_rps=models.CharField(u'Número RPS', max_length=15,null=True, default=0)

    coigo_servico=models.CharField(max_length=5, null=True, blank=True, default='104')
    codigo_cnae=models.CharField(max_length=8, null=True, blank=True, default='6202300')
    codigo_tributacao_municipio=models.CharField(max_length=15, null=True, blank=True, default='620230000')
    descr_tributacao_municipio = models.CharField(max_length=80, null=True, blank=True,
                                                  default='Desenvolvimento e licenciamento de programas de '
                                                          'computador customizáveis')
    empresa = models.OneToOneField('empresa.Empresa', on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.descricao}'

    class Meta:
        verbose_name_plural = 'Ambiente'
        permissions = (('ajustar_sequencias_ambiente','Pode ajustar sequências fiscais'),)
