from django.urls import path,include
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import EmpresaViewSet,SelecionarEmpresaView,OpcoesViewSet
router=SimpleRouter();router.register('empresas',EmpresaViewSet,basename='empresas-api');router.register('opcoes',OpcoesViewSet,basename='empresas-opcoes')
urlpatterns=[path('api/',include(router.urls)),path('api/selecionar/',SelecionarEmpresaView.as_view()),
 path('lista_empresa/',RedirectView.as_view(url='/clientes/app/empresas'),name='lista_empresas'),
 path('new_empresa/',EmpresaViewSet.as_view({'post':'create'}),name='new_empresa'),
 path('edit_empresa/<int:pk>/',EmpresaViewSet.as_view({'get':'retrieve','patch':'partial_update','put':'update'}),name='edit_empresa'),
 path('select_empresa/',SelecionarEmpresaView.as_view(),name='select_empresa')]
