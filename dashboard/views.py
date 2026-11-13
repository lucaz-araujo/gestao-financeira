from django.db import transaction
from django.shortcuts import redirect
from django.views.decorators.http import require_GET
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.api import empresa_da_requisicao
from usuario.models import Usuario
from usuario.services import auditar
from .serializers import CompetenciaSerializer, PeriodoSerializer, ResumoSerializer
from .services import competencia_atual, permissoes, resumo


class DashboardAPIView(APIView):
    authentication_classes = (JWTAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated,)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class ResumoView(DashboardAPIView):
    def get(self, request):
        empresa = empresa_da_requisicao(request)
        allowed = permissoes(request.user)
        if not any(allowed.values()):
            raise PermissionDenied('Sua conta não tem permissão para os indicadores deste painel.')
        serializer = PeriodoSerializer(data={**competencia_atual(request.user), **request.query_params.dict()})
        serializer.is_valid(raise_exception=True)
        return Response(ResumoSerializer(resumo(request.user, empresa, allowed, **serializer.validated_data)).data)


class CompetenciaView(DashboardAPIView):
    def get(self, request):
        return Response(competencia_atual(request.user))

    @transaction.atomic
    def patch(self, request):
        user = Usuario.objects.select_for_update().get(pk=request.user.pk)
        serializer = CompetenciaSerializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        auditar(user, ['ultimo_mes', 'ultimo_ano'])
        return Response(serializer.data)

    def post(self, request):
        return self.patch(request)


@require_GET
def dashboard(request):
    return redirect('/clientes/app/dashboard')


@require_GET
def competencia_legada(request):
    return redirect('/clientes/app/dashboard')
