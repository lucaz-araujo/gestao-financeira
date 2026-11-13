from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import ContatoViewSet, OpcoesViewSet
router=SimpleRouter()
router.register('contatos',ContatoViewSet,basename='agenda-contatos')
router.register('opcoes',OpcoesViewSet,basename='agenda-opcoes')
urlpatterns=[path('api/',include(router.urls)),
 path('list/',RedirectView.as_view(url='/clientes/app/agenda'),name='list_contatos'),
 path('new/',ContatoViewSet.as_view({'post':'create'}),name='new_contato'),
 path('edit/<int:pk>/',ContatoViewSet.as_view({'get':'retrieve','patch':'partial_update','put':'update'}),name='edit_contato')]
