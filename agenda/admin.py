from django.contrib import admin
from .models import Contato,Email,Telefone
class AgendaAdmin(admin.ModelAdmin):
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        # Administração de órfãos é uma revisão explícita, somente para superusuários.
        if request.user.is_superuser:return qs
        prefix='' if self.model==Contato else 'contato__'
        qs=qs.filter(**{prefix+'cliente__empresa__in':request.user.empresas.all()})
        if request.user.uf_id:qs=qs.filter(**{prefix+'cliente__uf_id':request.user.uf_id})
        return qs
for model in (Contato,Email,Telefone):admin.site.register(model,AgendaAdmin)
