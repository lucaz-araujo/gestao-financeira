from django.urls import include, path
from rest_framework.routers import SimpleRouter
from . import views, auth_api, frontend

router = SimpleRouter()
router.register('clientes', views.ClienteViewSet, basename='clientes-api')
router.register('parceiros', views.ParceiroViewSet, basename='parceiros-api')
router.register('liberacoes', views.LiberacaoViewSet, basename='liberacoes-api')
router.register('bloqueios', views.LiberacaoDatasViewSet, basename='bloqueios-api')
router.register('opcoes', views.OpcoesViewSet, basename='opcoes-api')
router.register('bancos', views.BancoViewSet, basename='bancos-clientes-api')
router.register('ufs', views.UfViewSet, basename='ufs-api')
router.register('municipios', views.MunicipioViewSet, basename='municipios-api')
router.register('municipios-br', views.MunicipioBrViewSet, basename='municipios-br-api')

C = views.ClienteViewSet
P = views.ParceiroViewSet
L = views.LiberacaoViewSet
B = views.LiberacaoDatasViewSet

# Nomes mantidos para reverse() nos apps ainda não migrados. CRUD agora retorna JSON.
urlpatterns = [
    path('app/', frontend.index, name='clientes_frontend'),
    path('app/<path:route>', frontend.index),
    path('api/auth/csrf/', auth_api.CsrfView.as_view()),
    path('api/auth/login/', auth_api.LoginView.as_view()),
    path('api/auth/refresh/', auth_api.RefreshView.as_view()),
    path('api/auth/logout/', auth_api.LogoutView.as_view()),
    path('api/auth/me/', auth_api.MeView.as_view()),

    path('api/', include(router.urls)),
    path('list/', C.as_view({'get': 'list'}), name='list_clientes'),
    path('list/<int:parceiro_id>/', C.as_view({'get': 'list'}), name='list_clientes_parc'),
    path('new/', C.as_view({'post': 'create'}), name='new_cliente'),
    path('edit/<int:pk>/', C.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'post': 'update'}), name='edit_cliente'),
    path('excluir_cliente/<int:pk>/', C.as_view({'post': 'destroy', 'delete': 'destroy'}), name='excluir_cliente'),
    path('relclientes/', C.as_view({'get': 'relatorio'}), name='relclientes'),
    path('relclientesnasc/', C.as_view({'get': 'aniversariantes'}), name='relclientes_nasc'),
    path('relparceiros/', P.as_view({'get': 'relatorio'}), name='relparceiros'),
    path('list_parc/', P.as_view({'get': 'list'}), name='list_parceiros'),
    path('new_parc/', P.as_view({'post': 'create'}), name='new_parceiro'),
    path('edit_parc/<int:pk>/', P.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'post': 'update'}), name='edit_parceiro'),
    path('excluir_parc/<int:pk>/', P.as_view({'post': 'destroy', 'delete': 'destroy'}), name='excluir_parceiro'),
    path('list_bloqueios/', B.as_view({'get': 'list'}), name='list_clientes_blog'),
    path('new_bloq/', B.as_view({'post': 'create'}), name='new_cliente_bloq'),
    path('edit_bloq/<int:pk>/', B.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update', 'post': 'update'}), name='edit_cliente_bloq'),
    path('excluir_clientebloq/<int:pk>/', B.as_view({'post': 'destroy', 'delete': 'destroy'}), name='excluir_clientebloq'),
    path('cidade/<int:uf>', views.MunicipioViewSet.as_view({'get': 'options'}), name='cidade'),
    path('municipiobr/<str:uf>', views.MunicipioBrViewSet.as_view({'get': 'options'}), name='municipiobr'),
    path('retorna_municipio/', views.MunicipioViewSet.as_view({'get': 'select2'}), name='retorna_municipio'),
    path('list_lib/', L.as_view({'get': 'list'}), name='list_liberacao'),
    path('new_lib/', L.as_view({'post': 'create'}), name='new_liberacao'),
    path('update_chave/<int:pk>/', L.as_view({'post': 'atualizar_chave'}), name='update_chave'),
    path('delete_chave/<int:pk>/', L.as_view({'post': 'destroy', 'delete': 'destroy'}), name='delete_chave'),
    path('retorna_cep/', views.retorna_cep, name='retorna_cep'),
]
