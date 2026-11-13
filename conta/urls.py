from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import BancoViewSet, ContaViewSet, MovimentoViewSet, TransferenciaViewSet, OpcoesViewSet
router = SimpleRouter()
for prefix, view in [('bancos', BancoViewSet), ('contas', ContaViewSet), ('movimentos', MovimentoViewSet), ('transferencias', TransferenciaViewSet), ('opcoes', OpcoesViewSet)]:
    router.register(prefix, view, basename='conta-' + prefix)
urlpatterns = [path('api/', include(router.urls)), path('app/', RedirectView.as_view(url='/clientes/app/contas'), name='conta_frontend')]
for plural, singular, view in [('bancos', 'banco', BancoViewSet), ('contas', 'conta', ContaViewSet), ('mov', 'mov', MovimentoViewSet), ('trans', 'trans', TransferenciaViewSet)]:
    page = {'mov': 'movimentos', 'trans': 'transferencias'}.get(plural, plural)
    urlpatterns += [
        path(f'list_{plural}/', RedirectView.as_view(url=f'/clientes/app/{page}'), name=f'lista_{plural}'),
        path(f'new_{singular}/', view.as_view({'post': 'create'}), name=f'new_{singular}'),
        path(f'edit_{singular}/<int:pk>/', view.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update'}), name=f'edit_{singular}'),
    ]
urlpatterns += [path('delete_mov/<int:pk>/', MovimentoViewSet.as_view({'delete': 'destroy', 'post': 'destroy'}), name='delete_mov'),
    path('extorna_trans/', RedirectView.as_view(url='/clientes/app/transferencias'), name='extorna_trans')]
for route, mode in [('rel_movi', 'movimentos'), ('rel_cheque', 'cheques'), ('rel_transf', 'transferencias')]:
    urlpatterns.append(path(route+'/', RedirectView.as_view(url='/clientes/app/'+('transferencias' if mode=='transferencias' else 'movimentos')+'?relatorio='+mode), name=route))
