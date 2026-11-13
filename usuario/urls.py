from django.urls import path
from django.views.generic import RedirectView
from . import views
from rest_framework.routers import DefaultRouter
from django.urls import include
from .management_api import CadastroUsuarioViewSet
router = DefaultRouter()
router.register('usuarios', CadastroUsuarioViewSet, basename='cadastro-usuario')
P=views.PerfilViewSet
urlpatterns=[
 path('api/', include(router.urls)),
 path('api/perfil/',P.as_view({'get':'retrieve','patch':'partial_update','put':'update'}),name='perfil-api'),
 path('api/perfil/senha/',P.as_view({'post':'senha'},throttle_classes=(views.PasswordThrottle,))),
 path('api/recuperacao/solicitar/',views.RecoveryRequestView.as_view()),path('api/recuperacao/confirmar/',views.RecoveryConfirmView.as_view()),
 path('login/',views.login_view,name='login_view'),path('logout/',views.logout_view,name='logout_view'),
 path('list/',RedirectView.as_view(url='/clientes/app/usuarios'),name='list_usuario'),
 path('edit/<int:pk>/',P.as_view({'get':'retrieve','patch':'partial_update','put':'update'}),name='edit_usuario'),
 path('mudarsenha/',RedirectView.as_view(url='/clientes/app/perfil?senha=1'),name='mudarsenha'),
 path('esqueceusenha/',views.recuperar_legado,name='esqueceusenha'),
 path('esqueceusenhapwd/<str:token>/',views.recuperar_legado,name='esqueceusenhapwd')]
