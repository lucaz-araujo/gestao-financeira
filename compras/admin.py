from django.contrib import admin
from .models import Fornecedor,Unidade,Itens,Solicitacao,Orcamento,SolicitacaoItem,OrcamentoItens
class CompraAdmin(admin.ModelAdmin):
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        reviewer=request.user.has_perm('compras.autorizar_solicitacao') or request.user.has_perm('compras.finalizar_solicitacao')
        if self.model==SolicitacaoItem:
            qs=qs.filter(solicitacao__empresa__in=request.user.empresas.all())
            return qs if reviewer else qs.filter(solicitacao__user_solicitante=request.user)
        if self.model==OrcamentoItens:
            qs=qs.filter(orcamento__empresa__in=request.user.empresas.all())
            return qs if reviewer else qs.filter(orcamento__solicitacao__user_solicitante=request.user)
        qs=qs.filter(empresa__in=request.user.empresas.all())
        if not reviewer:
            if self.model==Solicitacao: qs=qs.filter(user_solicitante=request.user)
            if self.model==Orcamento: qs=qs.filter(solicitacao__user_solicitante=request.user)
        return qs
for model in (Fornecedor,Unidade,Itens,Solicitacao,Orcamento,SolicitacaoItem,OrcamentoItens):admin.site.register(model,CompraAdmin)
