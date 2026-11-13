from django.db import models
from clientes.models import Uf, Municipio


class Empresa(models.Model):
    def clean(self):
        from django.core.exceptions import ValidationError
        from .validation import cnpj_valido
        errors = {}
        if not self.cnpj or not cnpj_valido(self.cnpj):
            errors['cnpj'] = 'CNPJ inválido.'
        if not (self.razao or '').strip():
            errors['razao'] = 'Informe a razão social.'
        if self.cidade_id and (not self.uf_id or self.cidade.uf_id != self.uf_id):
            errors['cidade'] = 'O município deve pertencer à UF informada.'
        if errors:
            raise ValidationError(errors)

    cnpj = models.CharField(max_length=18)
    inscricao_municipal = models.CharField(max_length=18)
    razao = models.CharField(max_length=60)
    logo = models.FileField(upload_to='img')
    logo_nome = models.CharField(max_length=40)
    uf = models.ForeignKey(Uf,
                           null=True,
                           blank=False,
                           on_delete=models.PROTECT)
    cidade = models.ForeignKey(Municipio,
                               null=True,
                               blank=False,
                               on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.cnpj}-{self.razao}'
