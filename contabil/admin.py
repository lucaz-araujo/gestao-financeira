from django.contrib import admin
from .models import PlanoContas, CentroCusto, TipoDespesa, Lancamentos

class AccountingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def get_queryset(self, request):
        from django.db.models import Q
        qs = super().get_queryset(request)
        if self.model == TipoDespesa:
            return qs.filter(Q(conta__empresa__in=request.user.empresas.all())|Q(conta__isnull=True))
        if self.model == Lancamentos:
            return qs.filter(conta_origem__empresa__in=request.user.empresas.all(),conta_destino__empresa__in=request.user.empresas.all())
        return qs.filter(empresa__in=request.user.empresas.all())
for model in (PlanoContas,CentroCusto,TipoDespesa,Lancamentos): admin.site.register(model,AccountingAdmin)
