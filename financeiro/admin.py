from django.contrib import admin
from .models import DocDespesa, PagDespesa, DocReceita, RecReceita, FechamentoCaixa, OperacaoBaixa, Configuracao


class FinancialReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        prefix = 'receita__' if self.model == RecReceita else 'despesa__' if self.model == PagDespesa else ''
        qs = qs.filter(**{prefix+'empresa__in': request.user.empresas.all()})
        if request.user.uf_id and self.model in (DocReceita, RecReceita):
            qs = qs.filter(**{prefix+'cliente__uf_id': request.user.uf_id})
        return qs


for model in (DocDespesa, PagDespesa, DocReceita, RecReceita, FechamentoCaixa, OperacaoBaixa):
    admin.site.register(model, FinancialReadOnlyAdmin)
admin.site.register(Configuracao)
