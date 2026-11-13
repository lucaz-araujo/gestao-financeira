from django.contrib import admin
from .models import Empresa
@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
    def get_queryset(self,request):
        return super().get_queryset(request).filter(pk__in=request.user.empresas.values('pk'))
