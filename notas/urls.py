from django.urls import include, path
from django.views.generic import RedirectView
from rest_framework.routers import SimpleRouter
from .views import NotaViewSet, portal_publico, link_legado

router = SimpleRouter()
router.register('notas', NotaViewSet, basename='notas-api')
front = RedirectView.as_view(url='/clientes/app/notas', permanent=False)
detail = RedirectView.as_view(url='/clientes/app/notas?nota=%(pk)s', permanent=False)
urlpatterns = [
    path('', front), path('app/', front, name='notas_frontend'),
    path('api/', include(router.urls)),
    path('publica/<str:token>/', portal_publico, name='nota_publica'),
    path('nf/<str:Id>/', link_legado, name='list_nf'),
    path('list/', front, name='list_notas'),
    path('new/', NotaViewSet.as_view({'post': 'create'}), name='new_nota'),
    path('edit/<int:pk>/', NotaViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'put': 'update'}), name='edit_nota'),
    path('excluir/<int:pk>/', NotaViewSet.as_view({'delete': 'destroy'}), name='excluir_nota'),
    path('gerarnotas/', NotaViewSet.as_view({'post': 'gerar'}), name='gerar_nota'),
    path('gerar_financeiro/<int:pk>/', NotaViewSet.as_view({'post': 'financeiro'}), name='financeiro_nota'),
    path('consultanota/<int:pk>/', NotaViewSet.as_view({'post': 'consultar'}), name='consulta_nota'),
    path('reenviarnota/<int:pk>/', NotaViewSet.as_view({'post': 'emitir'}), name='enviar_nota'),
    path('enviarcliente/<int:pk>/', NotaViewSet.as_view({'post': 'email'}), name='enviarcliente'),
    path('montanota/<int:pk>/', detail, name='monta_nota'),
    path('imprimirnota/<int:pk>/', detail, name='imprimir_nota'),
    path('consultalote/<str:pk>/', front, name='consulta_lote'),
    path('nf_email/<int:pk>/', front, name='nf_email'),
    path('relnotas/', RedirectView.as_view(url='/clientes/app/relatorios?tipo=NF_ALL'), name='rel_notas'),
    path('relnotaspagas/', RedirectView.as_view(url='/clientes/app/relatorios?tipo=NF_PAID'), name='rel_notas_pagas'),
]
for route, name in [('emitirnotas/', 'pesquisa_nota'), ('cancelarnotas/', 'pesquisa_nota_can'), ('concelar/', 'cancelar_nota'), ('consultanfse/', 'consulta_nfse'), ('emailsnota/', 'pesquisa_nota_emails'), ('emailsnota2/', 'emails_nota')]:
    urlpatterns.append(path(route, front, name=name))
