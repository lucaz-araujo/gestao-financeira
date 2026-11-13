from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import ReceitaViewSet, DespesaViewSet, FechamentoViewSet, OpcoesViewSet

router = SimpleRouter()
for prefix, view in [('receitas', ReceitaViewSet), ('despesas', DespesaViewSet), ('fechamentos', FechamentoViewSet), ('opcoes', OpcoesViewSet)]:
    router.register(prefix, view, basename='financeiro-'+prefix)
urlpatterns = [path('api/', include(router.urls)), path('app/', RedirectView.as_view(url='/clientes/app/receitas'))]
for route, name, target in [
    ('lista_receitas/', 'lista_receitas', 'receitas'), ('lista_despesas/', 'lista_despesas', 'despesas'),
    ('lista_fechamentos/', 'lista_fechamentos', 'fechamentos'), ('baixar_receitas/', 'baixar_receitas', 'receitas?conciliar=1'),
    ('baixar_confirma/', 'baixar_confirma', 'receitas?conciliar=1'),
    ('rel_contas_receber/', 'rel_contareceber', 'receitas'), ('rel_contas_pagar/', 'rel_contapagar', 'despesas'),
    ('rel_contas_pagar2/', 'rel_contapagar2', 'despesas'), ('rel_inadiplentes/', 'rel_inadiplentes', 'receitas?situacao=vencido'),
    ('rel_analise/', 'rel_analise', 'fechamentos?analise=1'),
]:
    urlpatterns.append(path(route, RedirectView.as_view(url='/clientes/app/'+target), name=name))
for prefix, view, single in [('receitas', ReceitaViewSet, 'receita'), ('despesas', DespesaViewSet, 'despesa')]:
    urlpatterns += [path('new_'+single+'/', view.as_view({'post': 'create'}), name='new_'+single),
        path('edit_'+single+'/<int:pk>/', view.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update'}), name='edit_'+single)]
# As antigas ações por documento levam à revisão; o estorno novo exige o ID de uma baixa específica.
for route, name, target in [('receber_receita', 'receber_receita', 'receitas'), ('pagar_despesa', 'pagar_despesa', 'despesas'),
    ('extorna_receita', 'extorna_recebido', 'receitas'), ('extorna_pago', 'extorna_pago', 'despesas'),
    ('duplicar_despesa', 'duplicar_despesa', 'despesas'), ('delete_despesa', 'delete_despesa', 'despesas'),
    ('delete_fechamento', 'delete_fechamento', 'fechamentos'), ('calcula_fechamento', 'calcula_fechamento', 'fechamentos')]:
    urlpatterns.append(path(route+'/<int:pk>/', RedirectView.as_view(url='/clientes/app/'+target), name=name))
