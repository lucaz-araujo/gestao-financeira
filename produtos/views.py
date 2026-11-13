"""CRUD JSON de produtos e serviços, limitado às empresas autorizadas."""
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.utils.functional import cached_property
from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.api import empresa_da_requisicao
from .models import Produto
from .serializers import ProdutoSerializer


class ProdutoPermissions(DjangoModelPermissions):
    perms_map = {**DjangoModelPermissions.perms_map,
                 'GET': ['%(app_label)s.view_%(model_name)s'],
                 'HEAD': ['%(app_label)s.view_%(model_name)s']}

    def get_required_permissions(self, method, model_cls):
        # As rotas antigas aceitam POST para editar/excluir: a permissão segue a ação.
        method = {'update': 'PUT', 'partial_update': 'PATCH', 'destroy': 'DELETE'}.get(self.view.action, method)
        return super().get_required_permissions(method, model_cls)

    def has_permission(self, request, view):
        self.view = view
        return super().has_permission(request, view)


class ProdutoPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class ProdutoConflict(APIException):
    status_code = 409
    default_code = 'conflict'
    default_detail = 'Exclusão impedida: o produto está vinculado a contratos ou liberações.'


class ProdutoViewSet(viewsets.ModelViewSet):
    queryset = Produto.objects.all()
    serializer_class = ProdutoSerializer
    authentication_classes = (JWTAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated, ProdutoPermissions)
    pagination_class = ProdutoPagination

    @cached_property
    def empresa_id(self):
        return empresa_da_requisicao(self.request)

    def get_queryset(self):
        qs = super().get_queryset().filter(empresa_id=self.empresa_id)
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(descricao__icontains=search) | Q(sigla__icontains=search))
        tipo = self.request.query_params.get('tipo_produto')
        if tipo:
            if tipo not in ('P', 'S'):
                raise ValidationError({'tipo_produto': 'Escolha P (Produto) ou S (Serviço).'})
            qs = qs.filter(tipo_produto=tipo)
        return qs.order_by('descricao', 'pk')

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(empresa_id=self.empresa_id)

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

    def handle_exception(self, exc):
        if isinstance(exc, ProtectedError):
            exc = ProdutoConflict()
        elif isinstance(exc, IntegrityError):
            exc = ProdutoConflict('Não foi possível gravar: o registro conflita com dados existentes.')
        return super().handle_exception(exc)
