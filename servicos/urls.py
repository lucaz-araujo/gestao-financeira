from django.urls import path, include
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import ServicoViewSet, OpcoesViewSet
router = SimpleRouter()
router.register('servicos', ServicoViewSet, basename='servicos-api')
router.register('opcoes', OpcoesViewSet, basename='servicos-opcoes')
urlpatterns = [
    path('api/', include(router.urls)),
    path('list/', RedirectView.as_view(url='/clientes/app/servicos'), name='list_servico'),
    path('new/', ServicoViewSet.as_view({'post':'create'}), name='new_servico'),
    path('edit/<int:pk>/', ServicoViewSet.as_view({'get':'retrieve','patch':'partial_update','put':'update'}), name='edit_servico'),
    path('delete_servico/<int:pk>/', ServicoViewSet.as_view({'delete':'destroy'}), name='delete_servico'),
]
