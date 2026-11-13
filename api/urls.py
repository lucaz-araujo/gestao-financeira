# -*- coding: utf-8 -*-
__author__ = 'Marcio'

from django.urls import re_path
from api import views

urlpatterns = [
    re_path(r'^libera/$', views.liberames, name='api_libera'),
    re_path(r'^libera_delphi/$', views.liberames_delphi, name='api_libera_delphi'),
    re_path(r'^recad_delphi/$', views.recad_delphi, name='api_recad_delphi'),
    re_path(r'^bloqueia/$', views.bloqueia, name='api_bloqueia'),
    re_path(r'^libera_servicos/$', views.liberames_servico, name='api_servico'),
    re_path(r'^libera_transparencia/$', views.libera_transparencia, name='api_transparencia'),

    # Integração com folha de pagamento web
    re_path(r'^cod_entidade/$', views.cod_entidade, name='api_entidade'),
]
