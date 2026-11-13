from django.contrib import admin
from django.db.models import F
from .models import ChaveServico
@admin.register(ChaveServico)
class ChaveAdmin(admin.ModelAdmin):
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        if request.user.is_superuser:return qs
        qs=qs.filter(cliente__empresa__in=request.user.empresas.all(),servico__cliente_id=F('cliente_id'),servico__empresa_id=F('cliente__empresa_id'))
        return qs.filter(cliente__uf_id=request.user.uf_id) if request.user.uf_id else qs
