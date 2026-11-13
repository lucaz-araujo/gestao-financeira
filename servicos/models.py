from django.db import models


# Create your models here.
class Servico(models.Model):
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.cliente_id and self.cliente.empresa_id != self.empresa_id:
            raise ValidationError({'cliente': 'O cliente deve pertencer à empresa do serviço.'})

    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    cliente = models.ForeignKey('clientes.Cliente',
                                related_name='clentes_servicos',
                                on_delete=models.PROTECT)
    descricao = models.CharField(max_length=100, unique=True)
    usuario = models.ForeignKey('usuario.Usuario',
                                null=True,
                                on_delete=models.PROTECT)

    def __str__(self):
        return '{}'.format(self.descricao)

    class Meta:
        verbose_name_plural = 'Servicos'
