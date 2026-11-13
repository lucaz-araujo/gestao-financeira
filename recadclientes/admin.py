from django.contrib import admin
from .models import EntidadeRecad, MODELOS_RECAD


class RecadAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        prefix = '' if self.model == EntidadeRecad else 'entidade__'
        qs = qs.filter(**{prefix + 'cliente__empresa__in': request.user.empresas.all()})
        if request.user.uf_id:
            qs = qs.filter(**{prefix + 'cliente__uf_id': request.user.uf_id})
        return qs


for model in MODELOS_RECAD:
    admin.site.register(model, RecadAdmin)
