"""Cadastro de contas comuns, independente da API de perfil pessoal."""
import hashlib
from django.db import connection, transaction, IntegrityError
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from core.api import empresa_da_requisicao
from .access import permissoes_delegaveis
from .models import Usuario
from .serializers import CadastroUsuarioSerializer
from rest_framework.throttling import UserRateThrottle


class CadastroThrottle(UserRateThrottle):
    rate = '30/min'
    scope = 'usuario-cadastro'


class CadastroPermission(BasePermission):
    def has_permission(self, request, view):
        if view.action == 'create':
            return request.user.has_perm('usuario.add_usuario')
        return request.user.has_perm('usuario.view_usuario') or request.user.has_perm('usuario.add_usuario')


class CadastroPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


@method_decorator(sensitive_post_parameters('password', 'conf_password'), name='dispatch')
class CadastroUsuarioViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated, CadastroPermission)
    serializer_class = CadastroUsuarioSerializer
    pagination_class = CadastroPagination
    throttle_classes = (CadastroThrottle,)
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        company = empresa_da_requisicao(self.request)
        # Oculta integralmente contas com vínculos fora do escopo do responsável.
        through = Usuario.empresas.through
        outside = through.objects.exclude(empresa_id__in=self.request.user.empresas.values('pk')).values('usuario_id')
        qs = Usuario.objects.filter(empresas=company, is_staff=False, is_superuser=False).exclude(pk__in=outside).prefetch_related('empresas', 'user_permissions').order_by('username', 'pk')
        search = self.request.query_params.get('search', '').strip()[:150]
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search))
        return qs

    @action(detail=False, methods=['get'])
    def opcoes(self, request):
        empresa_da_requisicao(request)
        actions = {'view': 'Visualizar', 'add': 'Cadastrar', 'change': 'Alterar', 'delete': 'Excluir'}
        permissions = []
        for permission in permissoes_delegaveis(request.user):
            model = permission.content_type.model_class()
            label = str(model._meta.verbose_name) if model else permission.content_type.model
            permissions.append({'id': permission.pk, 'codigo': f'{permission.content_type.app_label}.{permission.codename}', 'modulo': permission.content_type.app_label, 'nome': f"{actions[permission.codename.split('_', 1)[0]]} {label}"})
        return Response({'empresas': list(request.user.empresas.order_by('razao').values('id', 'razao', 'cnpj')), 'permissoes': permissions, 'uf': request.user.uf_id})

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # Reavalia a autorização com o cadastro atual do responsável.
        request.user = Usuario.objects.select_for_update().get(pk=request.user.pk)
        if not request.user.is_active:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Conta inativa.')
        self.check_permissions(request)
        empresa_da_requisicao(request)
        if connection.vendor == 'postgresql':
            identities = ['usuario.email:' + str(request.data.get('email', '')).strip().casefold(), 'usuario.username:' + str(request.data.get('username', '')).strip().casefold()]
            with connection.cursor() as cursor:
                for identity in sorted(identities):
                    lock = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], 'big') & ((1 << 63) - 1)
                    cursor.execute('SELECT pg_advisory_xact_lock(%s)', [lock])
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        from auditlog.models import LogEntry
        user = serializer.save()
        LogEntry.objects.log_create(user, action=LogEntry.Action.CREATE, actor=self.request.user, serialized_data=None, changes={
            'cadastro': [None, 'Usuário cadastrado'],
            'empresas': [None, list(user.empresas.values_list('pk', flat=True))],
            'permissoes': [None, list(user.user_permissions.values_list('pk', flat=True))],
        })

    def handle_exception(self, exc):
        if isinstance(exc, IntegrityError):
            exc = ValidationError('Dados indisponíveis para cadastro. Revise usuário e e-mail.')
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response
