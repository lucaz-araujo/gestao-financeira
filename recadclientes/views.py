from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from conta.views import BaseViewSet, Pagination
from core.api import empresa_da_requisicao
from clientes.models import Uf, Municipio
from servicos.serializers import clientes_visiveis
from .models import EntidadeRecad, UsuarioRecad, ContadorRecad, ControladorRecad, PrefeitoRecad, VicePrefeitoRecad, MODELOS_RECAD
from .serializers import (EntidadeRecadSerializer, UsuarioRecadSerializer, ContadorRecadSerializer,
    ControladorRecadSerializer, PrefeitoRecadSerializer, VicePrefeitoRecadSerializer, entidades_visiveis)


class RecadPermission(BasePermission):
    def has_permission(self, request, view):
        verb = {'create': 'add', 'update': 'change', 'partial_update': 'change', 'destroy': 'delete'}.get(view.action, 'view')
        return request.user.has_perm(f'recadclientes.{verb}_{view.queryset.model._meta.model_name}')


class RecadViewSet(BaseViewSet):
    permission_classes = (IsAuthenticated, RecadPermission)

    def base_queryset(self):
        if self.queryset.model == EntidadeRecad:
            return self.queryset.filter(pk__in=entidades_visiveis(self.empresa_id, self.request.user))
        return self.queryset.filter(entidade__in=entidades_visiveis(self.empresa_id, self.request.user))

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list':
            if self.queryset.model == EntidadeRecad:
                filters = ('cliente',)
            else:
                filters = ('entidade',)
            for field in filters:
                if self.request.query_params.get(field):
                    qs = qs.filter(**{field + '_id': serializers.IntegerField(min_value=1).run_validation(self.request.query_params[field])})
        return qs

    def perform_create(self, serializer):
        serializer.save()

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class EntidadeRecadViewSet(RecadViewSet):
    queryset = EntidadeRecad.objects.select_related('cliente', 'uf', 'cidade').order_by('nome', 'pk')
    serializer_class = EntidadeRecadSerializer
    search_fields = ('nome', 'codigo', 'tipo', 'cliente__instituicao')


class ResponsavelViewSet(RecadViewSet):
    search_fields = ('nome_completo', 'email', 'entidade__nome')


class UsuarioRecadViewSet(ResponsavelViewSet):
    queryset = UsuarioRecad.objects.select_related('entidade').order_by('nome_completo', 'pk')
    serializer_class = UsuarioRecadSerializer
    search_fields = ResponsavelViewSet.search_fields + ('cargo',)


class ContadorRecadViewSet(ResponsavelViewSet):
    queryset = ContadorRecad.objects.select_related('entidade').order_by('nome_completo', 'pk')
    serializer_class = ContadorRecadSerializer


class ControladorRecadViewSet(ResponsavelViewSet):
    queryset = ControladorRecad.objects.select_related('entidade').order_by('nome_completo', 'pk')
    serializer_class = ControladorRecadSerializer


class PrefeitoRecadViewSet(ResponsavelViewSet):
    queryset = PrefeitoRecad.objects.select_related('entidade').order_by('nome_completo', 'pk')
    serializer_class = PrefeitoRecadSerializer


class VicePrefeitoRecadViewSet(ResponsavelViewSet):
    queryset = VicePrefeitoRecad.objects.select_related('entidade').order_by('nome_completo', 'pk')
    serializer_class = VicePrefeitoRecadSerializer


class OpcoesViewSet(viewsets.GenericViewSet):
    authentication_classes = BaseViewSet.authentication_classes
    permission_classes = (IsAuthenticated,)
    pagination_class = Pagination

    def list(self, request):
        company = empresa_da_requisicao(request)
        kind = request.query_params.get('tipo', 'clientes')
        if kind in ('clientes', 'ufs', 'municipios'):
            models = (EntidadeRecad,)
        elif kind == 'entidades':
            models = MODELOS_RECAD[1:]
        else:
            raise ValidationError({'tipo': 'Opção inválida.'})
        if not any(request.user.has_perm(f'recadclientes.{verb}_{model._meta.model_name}') for model in models for verb in ('view', 'add', 'change')):
            raise PermissionDenied('Sem permissão para consultar estas opções de recadastramento.')
        if kind == 'clientes':
            qs, field = clientes_visiveis(company, request.user), 'instituicao'
        elif kind == 'entidades':
            qs, field = entidades_visiveis(company, request.user), 'nome'
        elif kind == 'ufs':
            qs, field = Uf.objects.all(), 'sigla'
        else:
            qs, field = Municipio.objects.all(), 'descricao'
            if request.query_params.get('uf'):
                qs = qs.filter(uf_id=serializers.IntegerField(min_value=1).run_validation(request.query_params['uf']))
        if request.query_params.get('search'):
            qs = qs.filter(**{field + '__icontains': request.query_params['search']})
        if request.query_params.get('id'):
            qs = qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
        return self.get_paginated_response([{'id': obj.pk, 'descricao': getattr(obj, field)} for obj in self.paginate_queryset(qs.order_by(field, 'pk'))])
