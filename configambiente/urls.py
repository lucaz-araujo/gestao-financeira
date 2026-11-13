from django.urls import path,include
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import AmbienteViewSet
router=SimpleRouter();router.register('ambientes',AmbienteViewSet,basename='ambientes-api')
urlpatterns=[path('api/',include(router.urls)),path('list/',RedirectView.as_view(url='/clientes/app/ambiente-fiscal'),name='list_ambiente'),
 path('edit/<int:pk>/',AmbienteViewSet.as_view({'get':'retrieve','patch':'partial_update','put':'update'}),name='edit_ambiente')]
