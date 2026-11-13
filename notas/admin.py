from django.contrib import admin
from .models import Nota, OperacaoFiscal


class FiscalReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Nota)
class NotaAdmin(FiscalReadOnlyAdmin):
    search_fields = ['numero']
    ordering = ['-dt_data_emissao']
    list_display = ['id', 'numero', 'empresa', 'competencia', 'exercicio']


@admin.register(OperacaoFiscal)
class OperacaoFiscalAdmin(FiscalReadOnlyAdmin):
    list_display = ['id', 'nota', 'acao', 'estado', 'usuario', 'criada_em']
    list_filter = ['estado', 'acao']
