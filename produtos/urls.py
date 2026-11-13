from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import ProdutoViewSet

router = SimpleRouter()
router.register('produtos', ProdutoViewSet, basename='produtos-api')

urlpatterns = [
    path('', RedirectView.as_view(url='/clientes/app/produtos', permanent=False)),
    path('app/', RedirectView.as_view(url='/clientes/app/produtos', permanent=False), name='produtos_frontend'),
    path('api/', include(router.urls)),
    path('list/', ProdutoViewSet.as_view({'get': 'list'}), name='list_produtos'),
    path('new/', ProdutoViewSet.as_view({'post': 'create'}), name='new_produto'),
    path('edit/<int:pk>/', ProdutoViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'post': 'update'}), name='edit_produto'),
    path('excluir/<int:pk>/', ProdutoViewSet.as_view({'delete': 'destroy', 'post': 'destroy'}), name='excluir_produto'),
]
