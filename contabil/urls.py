from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import PlanoViewSet, CentroViewSet, TipoViewSet, LancamentoViewSet, OpcoesViewSet
router = SimpleRouter()
urlpatterns = []
for prefix, view, old, listname, single in [
    ('planos',PlanoViewSet,'plconta','lista_plconta','plconta'),
    ('centros',CentroViewSet,'centro','lista_cc','cc'),
    ('tipos',TipoViewSet,'tipod','lista_tipd','tipd'),
    ('lancamentos',LancamentoViewSet,'lanca','lista_lancamentos','lancamento')]:
    router.register(prefix,view,basename='contabil-'+prefix)
    urlpatterns.extend([path('list_'+old+'/',RedirectView.as_view(url='/clientes/app/contabil-'+prefix),name=listname),
        path('new_'+old+'/',view.as_view({'post':'create'}),name='new_'+single),
        path('edit_'+old+'/<int:pk>/',view.as_view({'get':'retrieve','patch':'partial_update','put':'update'}),name='edit_'+single)])
router.register('opcoes',OpcoesViewSet,basename='contabil-opcoes')
urlpatterns.append(path('api/',include(router.urls)))
