from django.core.exceptions import ValidationError as ModelValidationError
from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from conta.views import BaseViewSet, Pagination
from core.api import empresa_da_requisicao
from servicos.serializers import clientes_visiveis
from clientes.models import Uf, Municipio
from .models import Contato, Email, Telefone
from .serializers import ContatoSerializer
from .services import save_contact, permission


class AgendaPermission(BasePermission):
    def has_permission(self,request,view):
        verb={'create':'add','update':'change','partial_update':'change','destroy':'delete'}.get(view.action,'view')
        return request.user.has_perm(f'agenda.{verb}_contato')


class ContatoViewSet(BaseViewSet):
    queryset=Contato.objects.select_related('cliente','cidade','uf').prefetch_related('Emails','Telefones').order_by('nome','pk')
    serializer_class=ContatoSerializer
    permission_classes=(IsAuthenticated,AgendaPermission)
    search_fields=('nome','cargo','cliente__instituicao')
    def base_queryset(self):
        return self.queryset.filter(cliente__in=clientes_visiveis(self.empresa_id,self.request.user))
    def get_queryset(self):
        qs=super().get_queryset()
        if self.action=='list' and self.request.query_params.get('cliente'):
            qs=qs.filter(cliente_id=serializers.IntegerField(min_value=1).run_validation(self.request.query_params['cliente']))
        return qs
    def perform_create(self,serializer):save_contact(serializer,self.request.user)
    def perform_update(self,serializer):save_contact(serializer,self.request.user)
    def perform_destroy(self,instance):
        for model in (Email,Telefone):
            if model.objects.filter(contato=instance).exists():
                permission(self.request.user,'delete',model);model.objects.filter(contato=instance).delete()
        instance.delete()
    def handle_exception(self,exc):
        if isinstance(exc,ModelValidationError):exc=ValidationError(exc.message_dict)
        return super().handle_exception(exc)


class OpcoesViewSet(viewsets.GenericViewSet):
    authentication_classes=BaseViewSet.authentication_classes
    permission_classes=(IsAuthenticated,)
    pagination_class=Pagination
    def list(self,request):
        company=empresa_da_requisicao(request)
        if not any(request.user.has_perm(f'agenda.{verb}_contato') for verb in ('view','add','change')):
            raise PermissionDenied('Sem permissão para consultar opções da agenda.')
        kind=request.query_params.get('tipo','clientes')
        if kind=='clientes':qs,field=clientes_visiveis(company,request.user),'instituicao'
        elif kind=='ufs':qs,field=Uf.objects.all(),'sigla'
        elif kind=='municipios':
            qs,field=Municipio.objects.all(),'descricao'
            if request.query_params.get('uf'):qs=qs.filter(uf_id=serializers.IntegerField(min_value=1).run_validation(request.query_params['uf']))
        else:raise ValidationError({'tipo':'Opção inválida.'})
        if request.query_params.get('id'):qs=qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
        if request.query_params.get('search'):qs=qs.filter(**{field+'__icontains':request.query_params['search']})
        return self.get_paginated_response([{'id':obj.pk,'descricao':obj.instituicao if kind=='clientes' else str(obj)} for obj in self.paginate_queryset(qs.order_by(field,'pk'))])
