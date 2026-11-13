from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework import viewsets, serializers
from conta.views import BaseViewSet, Pagination
from core.api import empresa_da_requisicao
from .models import Servico
from .serializers import ServicoSerializer, clientes_visiveis


class ServicoPermission(BasePermission):
    def has_permission(self, request, view):
        verb = {'create':'add', 'update':'change', 'partial_update':'change', 'destroy':'delete'}.get(view.action, 'view')
        return request.user.has_perm(f'servicos.{verb}_servico')


class ServicoViewSet(BaseViewSet):
    queryset = Servico.objects.select_related('cliente', 'usuario').order_by('descricao', 'pk')
    serializer_class = ServicoSerializer
    permission_classes = (IsAuthenticated, ServicoPermission)
    search_fields = ('descricao', 'cliente__instituicao')
    def base_queryset(self):
        return super().base_queryset().filter(cliente__in=clientes_visiveis(self.empresa_id, self.request.user))
    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list' and self.request.query_params.get('cliente'):
            qs = qs.filter(cliente_id=serializers.IntegerField(min_value=1).run_validation(self.request.query_params['cliente']))
        return qs
    def perform_create(self, serializer):
        serializer.save(empresa_id=self.empresa_id, usuario=self.request.user)
    def perform_update(self, serializer):
        serializer.save(usuario=self.request.user)


class OpcoesViewSet(viewsets.GenericViewSet):
    authentication_classes = BaseViewSet.authentication_classes
    permission_classes = (IsAuthenticated,)
    pagination_class = Pagination
    def list(self, request):
        company = empresa_da_requisicao(request)
        if not any(request.user.has_perm(f'servicos.{verb}_servico') for verb in ('view','add','change')):
            raise PermissionDenied('Sem permissão para consultar clientes de serviços.')
        qs = clientes_visiveis(company, request.user)
        if request.query_params.get('search'):
            qs = qs.filter(instituicao__icontains=request.query_params['search'])
        if request.query_params.get('id'):
            qs = qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
        return self.get_paginated_response([{'id':obj.pk, 'instituicao':obj.instituicao} for obj in self.paginate_queryset(qs.order_by('instituicao','pk'))])
