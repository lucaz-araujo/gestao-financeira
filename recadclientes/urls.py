from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from . import views
router = SimpleRouter()
for route, view in [('entidades', views.EntidadeRecadViewSet), ('usuarios', views.UsuarioRecadViewSet),
                    ('contadores', views.ContadorRecadViewSet), ('controladores', views.ControladorRecadViewSet),
                    ('prefeitos', views.PrefeitoRecadViewSet), ('vice-prefeitos', views.VicePrefeitoRecadViewSet), ('opcoes', views.OpcoesViewSet)]:
    router.register(route, view, basename='recad-' + route)
urlpatterns = [path('api/', include(router.urls)), path('', RedirectView.as_view(url='/clientes/app/recadastramento'))]
