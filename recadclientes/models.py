import re
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, URLValidator
from django.db import models
from auditlog.registry import auditlog


def validar_comunicacao(instance):
    errors = {}
    phone = instance.telefone
    if phone and (not re.fullmatch(r'[+\d() .-]+', phone) or not 8 <= len(re.sub(r'\D', '', phone)) <= 15):
        errors['telefone'] = 'Informe um telefone com 8 a 15 dígitos.'
    if instance.email:
        try:
            EmailValidator()(instance.email)
        except ValidationError:
            errors['email'] = 'Informe um e-mail válido.'
    return errors


class EntidadeRecad(models.Model):
    cliente = models.ForeignKey('clientes.Cliente', related_name='recadastramentos', on_delete=models.PROTECT)
    codigo = models.CharField(max_length=4, null=True, blank=True)
    tipo = models.CharField(max_length=4, null=True, blank=True)
    nome = models.CharField(max_length=60)
    uf = models.ForeignKey('clientes.Uf', related_name='uf_entidade', on_delete=models.PROTECT, null=True, blank=True)
    cidade = models.ForeignKey('clientes.Municipio', related_name='cidade_entidade', on_delete=models.PROTECT, null=True, blank=True)
    telefone = models.CharField(max_length=15, null=True, blank=True)
    site = models.URLField(max_length=100, null=True, blank=True)
    email = models.EmailField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        errors = validar_comunicacao(self)
        if not self.cliente_id:
            errors['cliente'] = 'Selecione um cliente.'
        if not self.nome or not self.nome.strip():
            errors['nome'] = 'Informe o nome da entidade.'
        if self.cidade_id and (not self.uf_id or self.cidade.uf_id != self.uf_id):
            errors['cidade'] = 'O município deve pertencer à UF informada.'
        if self.site:
            try:
                URLValidator(schemes=['http', 'https'])(self.site)
            except ValidationError:
                errors['site'] = 'Informe um endereço HTTP ou HTTPS válido.'
        if errors:
            raise ValidationError(errors)

    class Meta:
        db_table = 'entidade_recad'
        ordering = ['nome', 'pk']
        verbose_name = 'Entidade de recadastramento'
        verbose_name_plural = 'Entidades de recadastramento'


class ResponsavelRecad(models.Model):
    nome_completo = models.CharField(max_length=60)
    telefone = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.nome_completo

    def clean(self):
        super().clean()
        errors = validar_comunicacao(self)
        if not self.nome_completo or not self.nome_completo.strip():
            errors['nome_completo'] = 'Informe o nome completo.'
        if not self.entidade_id:
            errors['entidade'] = 'Selecione uma entidade.'
        if errors:
            raise ValidationError(errors)

    class Meta:
        abstract = True
        ordering = ['nome_completo', 'pk']


class UsuarioRecad(ResponsavelRecad):
    entidade = models.ForeignKey(EntidadeRecad, related_name='usuarios', on_delete=models.PROTECT)
    cargo = models.CharField(max_length=60, null=True, blank=True)

    class Meta(ResponsavelRecad.Meta):
        abstract = False
        db_table = 'usuario_recad'
        verbose_name = 'Usuário da entidade'
        verbose_name_plural = 'Usuários das entidades'


class ContadorRecad(ResponsavelRecad):
    entidade = models.ForeignKey(EntidadeRecad, related_name='contadores', on_delete=models.PROTECT)

    class Meta(ResponsavelRecad.Meta):
        abstract = False
        db_table = 'contador_recad'
        verbose_name = 'Contador da entidade'
        verbose_name_plural = 'Contadores das entidades'


class ControladorRecad(ResponsavelRecad):
    entidade = models.ForeignKey(EntidadeRecad, related_name='controladores', on_delete=models.PROTECT)

    class Meta(ResponsavelRecad.Meta):
        abstract = False
        db_table = 'controlador_recad'
        verbose_name = 'Controlador da entidade'
        verbose_name_plural = 'Controladores das entidades'


class PrefeitoRecad(ResponsavelRecad):
    entidade = models.ForeignKey(EntidadeRecad, related_name='prefeitos', on_delete=models.PROTECT)

    class Meta(ResponsavelRecad.Meta):
        abstract = False
        db_table = 'prefeito_recad'
        verbose_name = 'Prefeito'
        verbose_name_plural = 'Prefeitos'


class VicePrefeitoRecad(ResponsavelRecad):
    entidade = models.ForeignKey(EntidadeRecad, related_name='vice_prefeitos', on_delete=models.PROTECT)

    class Meta(ResponsavelRecad.Meta):
        abstract = False
        db_table = 'viceprefeito_recad'
        verbose_name = 'Vice-prefeito'
        verbose_name_plural = 'Vice-prefeitos'


MODELOS_RECAD = (EntidadeRecad, UsuarioRecad, ContadorRecad, ControladorRecad, PrefeitoRecad, VicePrefeitoRecad)
for model in MODELOS_RECAD:
    auditlog.register(model)
