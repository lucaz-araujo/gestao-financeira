from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from rest_framework import serializers,viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission,IsAuthenticated
from rest_framework.exceptions import PermissionDenied,ValidationError
from rest_framework.response import Response
from conta.views import BaseViewSet,Pagination
from core.api import empresa_da_requisicao
from servicos.models import Servico
from servicos.serializers import clientes_visiveis
from .models import ChaveServico
from .serializers import ChaveServicoSerializer
from .services import gravar_chave


class ChavePermission(BasePermission):
    def has_permission(self,request,view):
        verb={'create':'add','update':'change','partial_update':'change','destroy':'delete','atualizar':'change'}.get(view.action,'view')
        return request.user.has_perm(f'chaves.{verb}_chaveservico') or (verb=='view' and request.user.has_perm('chaves.view_chaves'))


class ChaveViewSet(BaseViewSet):
    queryset=ChaveServico.objects.select_related('cliente','servico','usuario').order_by('-exercicio','-competencia','-pk')
    serializer_class=ChaveServicoSerializer
    permission_classes=(IsAuthenticated,ChavePermission)
    search_fields=('cliente__instituicao','servico__descricao')
    def base_queryset(self):
        # Registros sem serviço ou com vínculo antigo divergente ficam fora da API comum.
        from django.db.models import F
        return self.queryset.filter(cliente__in=clientes_visiveis(self.empresa_id,self.request.user),servico__empresa_id=self.empresa_id,servico__cliente_id=F('cliente_id'))
    def get_queryset(self):
        qs=super().get_queryset()
        for field in ('cliente','servico','exercicio'):
            if self.action=='list' and self.request.query_params.get(field):
                value=serializers.IntegerField(min_value=1900 if field=='exercicio' else 1,max_value=9999 if field=='exercicio' else None).run_validation(self.request.query_params[field])
                qs=qs.filter(**{field:value})
        if self.action=='list' and self.request.query_params.get('competencia'):
            value=serializers.IntegerField(min_value=1,max_value=12).run_validation(self.request.query_params['competencia'])
            qs=qs.filter(competencia=str(value).zfill(2))
        return qs
    def perform_create(self,serializer):gravar_chave(serializer,self.request.user,self.empresa_id)
    def perform_update(self,serializer):gravar_chave(serializer,self.request.user,self.empresa_id)
    @action(detail=True,methods=['post'])
    @transaction.atomic
    def atualizar(self,request,pk=None):
        from django.shortcuts import get_object_or_404
        obj=get_object_or_404(self.get_queryset().select_for_update(of=('self',)),pk=pk)
        serializer=self.get_serializer(obj,data={},partial=True);serializer.is_valid(raise_exception=True)
        gravar_chave(serializer,request.user,self.empresa_id)
        return Response(serializer.data)
    def handle_exception(self,exc):
        if isinstance(exc,ModelValidationError):exc=ValidationError(exc.message_dict)
        return super().handle_exception(exc)


class OpcoesViewSet(viewsets.GenericViewSet):
    authentication_classes=BaseViewSet.authentication_classes
    permission_classes=(IsAuthenticated,)
    pagination_class=Pagination
    def list(self,request):
        company=empresa_da_requisicao(request)
        if not (any(request.user.has_perm(f'chaves.{verb}_chaveservico') for verb in ('view','add','change')) or request.user.has_perm('chaves.view_chaves')):
            raise PermissionDenied('Sem permissão para consultar opções de chaves.')
        clients=clientes_visiveis(company,request.user)
        kind=request.query_params.get('tipo','clientes')
        if kind=='clientes':qs,field=clients,'instituicao'
        elif kind=='servicos':
            qs,field=Servico.objects.filter(empresa_id=company,cliente__in=clients),'descricao'
            if request.query_params.get('cliente'):qs=qs.filter(cliente_id=serializers.IntegerField(min_value=1).run_validation(request.query_params['cliente']))
        else:raise ValidationError({'tipo':'Escolha clientes ou serviços.'})
        if request.query_params.get('id'):qs=qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
        if request.query_params.get('search'):qs=qs.filter(**{field+'__icontains':request.query_params['search']})
        return self.get_paginated_response([{'id':obj.pk,'descricao':str(obj.instituicao if kind=='clientes' else obj.descricao)} for obj in self.paginate_queryset(qs.order_by(field,'pk'))])
