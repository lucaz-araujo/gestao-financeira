from django.contrib import admin
from contratos.models import *


class ContratoAdmin(admin.ModelAdmin):
    search_fields = ('cliente__instituicao', )
    list_filter = ['cliente', 'empresa']


admin.site.register(Contrato, ContratoAdmin)
admin.site.register(ContratoProduto)
