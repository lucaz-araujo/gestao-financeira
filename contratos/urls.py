from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import ContratoViewSet

router = SimpleRouter()
router.register('contratos', ContratoViewSet, basename='contratos-api')

urlpatterns = [
    path('', RedirectView.as_view(url='/clientes/app/contratos', permanent=False)),
    path('app/', RedirectView.as_view(url='/clientes/app/contratos', permanent=False), name='contratos_frontend'),
    path('api/', include(router.urls)),
    path('list/', ContratoViewSet.as_view({'get': 'list'}), name='list_contratos'),
    path('new/', ContratoViewSet.as_view({'post': 'create'}), name='new_contrato'),
    path('edit/<int:pk>/', ContratoViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'post': 'update'}), name='edit_contrato'),
    path('delete/<int:pk>/', ContratoViewSet.as_view({'delete': 'destroy', 'post': 'destroy'}), name='delete_contrato'),
    path('relcontratos/', ContratoViewSet.as_view({'get': 'relatorio'}), name='rel_contratos'),
    path('print/<int:pk>/', RedirectView.as_view(url='/clientes/app/contratos?imprimir=%(pk)s', permanent=False), name='print_contrato'),
]
