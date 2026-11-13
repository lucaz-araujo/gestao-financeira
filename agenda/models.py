from django.db import models


# Create your models here.
class Contato(models.Model):
    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if not self.cliente_id:
            errors['cliente'] = 'Vincule o contato a um cliente.'
        if not (self.nome or '').strip():
            errors['nome'] = 'Informe o nome do contato.'
        if self.cidade_id and (not self.uf_id or self.cidade.uf_id != self.uf_id):
            errors['cidade'] = 'O município deve pertencer à UF informada.'
        if errors:
            raise ValidationError(errors)

    cliente = models.ForeignKey('clientes.Cliente',
                                related_name='Contatos',
                                null=True,
                                blank=True,
                                on_delete=models.PROTECT)
    nome = models.CharField(max_length=60, null=True, blank=True)
    cargo = models.CharField(max_length=60, null=True, blank=True)
    logradouro = models.CharField(max_length=60, null=True, blank=True)
    bairro = models.CharField(max_length=30, null=True, blank=True)
    cidade = models.ForeignKey('clientes.Municipio',
                               null=True,
                               on_delete=models.PROTECT)
    uf = models.ForeignKey('clientes.Uf',
                           null=True,
                           on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.nome}'

    class Meta:
        ordering = ['nome']
        verbose_name_plural = 'Contatos'


class Email(models.Model):
    contato = models.ForeignKey(Contato,
                                related_name='Emails',
                                on_delete=models.PROTECT)
    email = models.EmailField(max_length=400)

    def __str__(self):
        return f'{self.email}'

    class Meta:
        verbose_name_plural = 'Emails'


class Telefone(models.Model):
    contato = models.ForeignKey(Contato,
                                related_name='Telefones',
                                null=True,
                                blank=True,
                                on_delete=models.PROTECT)
    fone = models.CharField(max_length=16)

    def __str__(self):
        return f'{self.fone}'

    class Meta:
        verbose_name_plural = 'Telefones'