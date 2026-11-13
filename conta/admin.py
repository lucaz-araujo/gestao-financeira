from django.contrib import admin
from .models import Banco, Conta, Movimento, Transferencia


class ContaReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self.model is not Banco and not request.user.is_superuser:
            qs = qs.filter(empresa__in=request.user.empresas.all())
        return qs


for model in (Banco, Conta, Movimento, Transferencia):
    admin.site.register(model, ContaReadOnlyAdmin)
