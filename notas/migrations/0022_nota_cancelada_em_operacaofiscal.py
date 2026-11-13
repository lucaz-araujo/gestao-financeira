import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notas', '0021_auto_20210622_1241'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='nota',
            name='cancelada_em',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.CreateModel(
            name='OperacaoFiscal',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('acao', models.CharField(choices=[('emitir', 'emitir'), ('consultar', 'consultar'), ('consultar_lote', 'consultar_lote'), ('cancelar', 'cancelar'), ('email', 'email'), ('email_cliente', 'email_cliente')], max_length=20)),
                ('chave', models.UUIDField()),
                ('estado', models.CharField(choices=[('executando', 'executando'), ('concluida', 'concluida'), ('falha', 'falha'), ('incerta', 'incerta')], default='executando', max_length=12)),
                ('resultado', models.JSONField(default=dict)),
                ('criada_em', models.DateTimeField(auto_now_add=True)),
                ('atualizada_em', models.DateTimeField(auto_now=True)),
                ('nota', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='operacoes', to='notas.nota')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-criada_em'],
                'indexes': [models.Index(fields=['nota', 'estado'], name='nota_operacao_estado_idx')],
                'constraints': [models.UniqueConstraint(fields=('nota', 'acao', 'chave'), name='nota_operacao_chave_unica')],
            },
        ),
    ]
