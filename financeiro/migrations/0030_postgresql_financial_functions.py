"""Versiona funções antes mantidas apenas no dump PostgreSQL."""
from pathlib import Path
from django.db import migrations

SQL_DIR = Path(__file__).resolve().parent.parent / 'sql'


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        for name in ('fechamento.sql', 'analise.sql'):
            schema_editor.execute((SQL_DIR / name).read_text(), params=None)


def backward(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute((SQL_DIR / 'legacy_functions.sql').read_text(), params=None)


class Migration(migrations.Migration):
    dependencies = [
        ('financeiro', '0029_auto_20210622_1241'),
        ('notas', '0020_auto_20190805_1612'),
        ('conta', '0016_auto_20190805_1612'),
        ('usuario', '0011_auto_20190805_1612'),
    ]
    operations = [migrations.RunPython(forward, backward)]
