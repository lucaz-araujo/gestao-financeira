from django.urls import path,include
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import ChaveViewSet,OpcoesViewSet
router=SimpleRouter();router.register('chaves',ChaveViewSet,basename='chaves-api');router.register('opcoes',OpcoesViewSet,basename='chaves-opcoes')
urlpatterns=[path('api/',include(router.urls)),path('list/',RedirectView.as_view(url='/clientes/app/chaves'),name='list_chaves'),
 path('new/',ChaveViewSet.as_view({'post':'create'}),name='new_chaves'),
 path('edit/<int:pk>/',ChaveViewSet.as_view({'get':'retrieve','put':'update','patch':'partial_update'}),name='edit_chaves'),
 path('delete_chave/<int:pk>/',ChaveViewSet.as_view({'delete':'destroy'}),name='delete_chave'),
 path('update_chave/<int:pk>/',ChaveViewSet.as_view({'post':'atualizar'}),name='update_chave')]
