from django.urls import include, re_path, path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from usuario import views as views_usuario
from clientes.auth_api import LimitedTokenObtainPairView, LimitedTokenRefreshView

urlpatterns = [
    path('api/token/', LimitedTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', LimitedTokenRefreshView.as_view(), name='token_refresh'),
    path("api-auth/", include("rest_framework.urls")),
    re_path(r'^$', views_usuario.login_view),
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^clientes/', include('clientes.urls')),
    re_path(r'^contratos/', include('contratos.urls')),
    re_path(r'^usuario/', include('usuario.urls')),
    path('recadclientes/', include('recadclientes.urls')),
    re_path(r'^dashboard/', include('dashboard.urls')),
    re_path(r'^produtos/', include('produtos.urls')),
    re_path(r'^notas/', include('notas.urls')),
    re_path(r'^configambiente/', include('configambiente.urls')),
    re_path(r'^compras/', include('compras.urls')),
    re_path(r'^conta/', include('conta.urls')),
    re_path(r'^financeiro/', include('financeiro.urls')),
    re_path(r'^contabil/', include('contabil.urls')),
    re_path(r'^agenda/', include('agenda.urls')),
    re_path(r'^chave/', include('chaves.urls')),
    re_path(r'^servico/', include('servicos.urls')),
    re_path(r'^empresa/', include('empresa.urls')),
    re_path(r'^api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
