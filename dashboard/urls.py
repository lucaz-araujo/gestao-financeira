from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('competencia/', views.competencia_legada),
    path('api/resumo/', views.ResumoView.as_view()),
    path('api/competencia/', views.CompetenciaView.as_view()),
]
