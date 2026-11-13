from django.db import models
from django.utils import timezone

def exercicio_atual():
    return timezone.localdate().year


# Create your models here.
class ChaveServico(models.Model):
    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if not self.servico_id:
            errors['servico'] = 'Informe o serviço.'
        elif self.cliente_id and (self.servico.cliente_id != self.cliente_id or self.servico.empresa_id != self.cliente.empresa_id):
            errors['servico'] = 'O serviço deve pertencer ao cliente e à sua empresa.'
        if self.competencia not in [str(month).zfill(2) for month in range(1,13)]:
            errors['competencia'] = 'Informe uma competência de 01 a 12.'
        if self.exercicio is None or not 1900 <= self.exercicio <= 9999:
            errors['exercicio'] = 'Informe um ano de quatro dígitos a partir de 1900.'
        if errors:
            raise ValidationError(errors)

    cliente = models.ForeignKey('clientes.Cliente',
                                related_name='chavesservico',
                                on_delete=models.PROTECT)
    competencia = models.CharField(max_length=2)
    exercicio = models.IntegerField(default=exercicio_atual)
    dt_liberacao = models.DateTimeField()
    chave = models.CharField(max_length=100, unique=True)
    usuario = models.ForeignKey('usuario.Usuario',
                                null=True,
                                on_delete=models.PROTECT)
    servico = models.ForeignKey('servicos.Servico',
                                related_name='servico',
                                null=True,
                                on_delete=models.PROTECT)

    def __str__(self):
        return f'{self.cliente.instituicao}'

    class Meta:
        ordering = ['exercicio','competencia']
        verbose_name_plural = 'ChaveServicos'
        permissions = (
            ('view_chaves', 'View Chaves'),
        )
