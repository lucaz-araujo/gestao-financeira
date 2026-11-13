from django.urls import path,include
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import FornecedorViewSet,UnidadeViewSet,ItemViewSet,SolicitacaoViewSet,OrcamentoViewSet,OpcoesViewSet
router=SimpleRouter();urlpatterns=[]
for prefix,view,old in [('fornecedores',FornecedorViewSet,'forn'),('unidades',UnidadeViewSet,'unidades'),('itens',ItemViewSet,'itens'),('solicitacoes',SolicitacaoViewSet,'solicitacao')]:
    router.register(prefix,view,basename='compras-'+prefix)
    urlpatterns.extend([path('list_'+old+'/',RedirectView.as_view(url='/clientes/app/compras-'+prefix),name='list_'+old),
        path('new_'+old+'/',view.as_view({'post':'create'}),name='new_'+old),
        path('edit_'+old+'/<int:pk>/',view.as_view({'get':'retrieve','patch':'partial_update','put':'update'}),name='edit_'+old)])
router.register('orcamentos',OrcamentoViewSet,basename='compras-orcamentos')
router.register('opcoes',OpcoesViewSet,basename='compras-opcoes')
urlpatterns.append(path('api/',include(router.urls)))
for route,name in [('list_orcamentos','list_orcamentos'),('edit_orcamento','edit_orcamento'),('new_orcamento','new_orcamento'),('delete_orcamento','delete_orcamento'),('imprimir_solicitacao','imprimir_solicitacao')]:
    urlpatterns.append(path(route+'/<int:pk>/',RedirectView.as_view(url='/clientes/app/compras-solicitacoes'),name=name))
for route,name in [('status_solicitacao','status_solicitacao'),('finalizar_solicitacao','finalizar_solicitacao')]:
    urlpatterns.append(path(route+'/',RedirectView.as_view(url='/clientes/app/compras-solicitacoes'),name=name))
