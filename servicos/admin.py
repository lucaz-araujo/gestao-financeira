from django.contrib import admin
from .models import Servico
@admin.register(Servico)
class ServicoAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def get_queryset(self, request):
        qs = super().get_queryset(request).filter(empresa__in=request.user.empresas.all(), cliente__empresa__in=request.user.empresas.all())
        from django.db.models import F
        qs = qs.filter(empresa_id=F('cliente__empresa_id'))
        return qs.filter(cliente__uf_id=request.user.uf_id) if request.user.uf_id else qs
