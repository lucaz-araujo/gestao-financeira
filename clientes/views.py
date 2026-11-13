"""API do app clientes; as rotas deste módulo retornam JSON."""
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils.functional import cached_property
from requests.exceptions import RequestException
from rest_framework import mixins, serializers, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .cep import busca_cep
from .models import Cliente, Parceiro, Uf, Municipio, MunicipioBr, Liberacao, LiberacaoDatas
from .serializers import (ClienteSerializer, ParceiroSerializer, UfSerializer,
                          MunicipioSerializer, MunicipioBrSerializer,
                          LiberacaoSerializer, LiberacaoDatasSerializer, ClienteReportSerializer, BancoSerializer)


class Conflict(APIException):
    status_code = 409
    default_detail = 'O registro possui vínculos ou conflita com outro cadastro.'
    default_code = 'conflict'


class ClientesPermission(BasePermission):
    def has_permission(self, request, view):
        action_name = view.action
        permission = view.permission_overrides.get(action_name)
        if permission is None:
            operation = {'create': 'add', 'update': 'change', 'partial_update': 'change',
                         'destroy': 'delete', 'atualizar_chave': 'change'}.get(action_name, 'view')
            permission = f'clientes.{operation}_{view.queryset.model._meta.model_name}'
        return request.user.has_perm(permission)


class ClientesPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


def integer(value, field, minimum=1, maximum=None):
    try:
        number = int(value)
        if number < minimum or (maximum is not None and number > maximum):
            raise ValueError
        return number
    except (ValueError, TypeError):
        raise ValidationError({field: 'Informe um número inteiro válido.'})


class ScopedViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated, ClientesPermission)
    permission_overrides = {}
    pagination_class = ClientesPagination
    empresa_field = 'empresa_id'
    uf_field = 'uf_id'

    @cached_property
    def empresa_id(self):
        value = self.request.headers.get('X-Empresa-ID')
        if value is None:
            value = self.request.query_params.get('empresa')
        if value is None:
            value = self.request.session.get('empresa')
        company_id = integer(value, 'empresa')
        # Mesmo superusuários escolhem uma empresa à qual estão vinculados.
        if not self.request.user.empresas.filter(pk=company_id).exists():
            raise PermissionDenied('Empresa fora do seu escopo de acesso.')
        return company_id

    def scoped(self, queryset, empresa_field='empresa_id', uf_field='uf_id'):
        queryset = queryset.filter(**{empresa_field: self.empresa_id})
        if self.request.user.uf_id:
            queryset = queryset.filter(**{uf_field: self.request.user.uf_id})
        return queryset

    def get_queryset(self):
        return self.scoped(super().get_queryset(), self.empresa_field, self.uf_field)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['clientes'] = self.scoped(Cliente.objects.all())
        context['parceiros'] = self.scoped(Parceiro.objects.all())
        return context

    def filter_ids(self, queryset, parameter, field):
        values = self.request.query_params.getlist(parameter)
        if values:
            ids = [integer(part, parameter) for value in values for part in value.split(',')]
            queryset = queryset.filter(**{f'{field}__in': ids})
        return queryset

    def handle_exception(self, exc):
        if isinstance(exc, ProtectedError):
            exc = Conflict('Exclusão impedida: existem registros vinculados.')
        elif isinstance(exc, IntegrityError):
            exc = Conflict()
        elif isinstance(exc, ModelValidationError):
            exc = ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
        return super().handle_exception(exc)

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        instance.delete()

    def report_response(self, queryset, serializer_class=None):
        page = self.paginate_queryset(queryset)
        serializer = (serializer_class or self.get_serializer_class())(
            page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)


class CadastroViewSet(ScopedViewSet, viewsets.ModelViewSet):
    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(empresa_id=self.empresa_id)

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self.filter_ids(qs, 'uf', 'uf_id')
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(instituicao__icontains=search)
        return qs.order_by('instituicao', 'pk')


class ClienteViewSet(CadastroViewSet):
    queryset = Cliente.objects.select_related('cidade', 'uf', 'parceiro', 'banco').all()
    serializer_class = ClienteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self.filter_ids(qs, 'cliente', 'pk')
        qs = self.filter_ids(qs, 'parceiro', 'parceiro_id')
        if self.kwargs.get('parceiro_id'):
            qs = qs.filter(parceiro_id=self.kwargs['parceiro_id'])
        for field in ('ativo', 'desativar'):
            if field in self.request.query_params:
                value = serializers.BooleanField().run_validation(self.request.query_params[field])
                qs = qs.filter(**{field: value})
        return qs

    @action(detail=False, methods=['get'])
    def relatorio(self, request, **kwargs):
        kind = request.query_params.get('tipo_relatorio', 'CL')
        if kind not in ('CL', 'CP', 'CC'):
            raise ValidationError({'tipo_relatorio': 'Escolha CL, CP ou CC.'})
        cls = ClienteSerializer if kind == 'CL' else ClienteReportSerializer
        return self.report_response(self.get_queryset().filter(desativar=False), cls)

    @action(detail=False, methods=['get'])
    def aniversariantes(self, request, **kwargs):
        month = integer(request.query_params.get('competencia'), 'competencia', maximum=12)
        return self.report_response(self.get_queryset().filter(
            desativar=False, dt_resp_nascimento__month=month))


class ParceiroViewSet(CadastroViewSet):
    queryset = Parceiro.objects.select_related('cidade', 'uf').all()
    serializer_class = ParceiroSerializer

    @action(detail=False, methods=['get'])
    def relatorio(self, request, **kwargs):
        return self.report_response(self.get_queryset())


class ClienteRelacionadoViewSet(ScopedViewSet):
    empresa_field = 'cliente__empresa_id'
    uf_field = 'cliente__uf_id'

    def get_queryset(self):
        qs = super().get_queryset()
        qs = self.filter_ids(qs, 'cliente', 'cliente_id')
        return self.filter_ids(qs, 'parceiro', 'cliente__parceiro_id')

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        serializer.save(usuario=self.request.user)


class LiberacaoViewSet(ClienteRelacionadoViewSet, mixins.ListModelMixin,
                       mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin):
    queryset = Liberacao.objects.select_related('cliente', 'usuario').order_by('-exercicio', '-competencia', '-pk')
    serializer_class = LiberacaoSerializer
    permission_overrides = {'list': 'financeiro.add_recreceita', 'retrieve': 'financeiro.add_recreceita',
                            'create': 'financeiro.add_recreceita'}

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def atualizar_chave(self, request, **kwargs):
        obj = self.get_object()
        obj.atualizar_chave()
        obj.save(update_fields=['chave', 'codigo', 'codigo_layout'])
        return Response(self.get_serializer(obj).data)


class LiberacaoDatasViewSet(ClienteRelacionadoViewSet, viewsets.ModelViewSet):
    queryset = LiberacaoDatas.objects.select_related('cliente', 'usuario').order_by('-dt_ate', '-pk')
    serializer_class = LiberacaoDatasSerializer


class ReferenciaViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = (JWTAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated,)
    pagination_class = ClientesPagination


class UfViewSet(ReferenciaViewSet):
    queryset = Uf.objects.order_by('sigla', 'pk')
    serializer_class = UfSerializer


class MunicipioViewSet(ReferenciaViewSet):
    queryset = Municipio.objects.order_by('descricao', 'pk')
    serializer_class = MunicipioSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        uf = self.kwargs.get('uf') or self.request.query_params.get('uf') or self.request.query_params.get('id')
        if uf:
            qs = qs.filter(uf_id=integer(uf, 'uf'))
        search = self.request.query_params.get('search', '')
        return qs.filter(descricao__icontains=search) if search else qs

    def options(self, request, **kwargs):
        return Response({'options': [{'value': obj.pk, 'text': obj.descricao} for obj in self.get_queryset()]})

    def select2(self, request, **kwargs):
        return Response([{'id': obj.pk, 'text': obj.descricao} for obj in self.get_queryset()])


class MunicipioBrViewSet(ReferenciaViewSet):
    queryset = MunicipioBr.objects.order_by('cidade', 'pk')
    serializer_class = MunicipioBrSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        uf = self.kwargs.get('uf') or self.request.query_params.get('uf')
        if uf:
            if str(uf).isdigit():
                state = Uf.objects.filter(pk=int(uf)).first()
                if state is None:
                    raise ValidationError({'uf': 'UF inválida.'})
                uf = state.sigla
            qs = qs.filter(ufmuni=uf.upper())
        return qs

    def options(self, request, **kwargs):
        return Response({'options': [{'value': obj.cdmunic, 'text': obj.cidade} for obj in self.get_queryset()]})


@api_view(['GET'])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def retorna_cep(request):
    address = request.query_params.get('logradouro', '').strip()
    if not address:
        raise ValidationError({'logradouro': 'Informe o endereço para consulta.'})
    try:
        return Response({'results': busca_cep(address)})
    except (RequestException, IndexError, TypeError):
        return Response({'detail': 'Serviço de consulta de CEP indisponível.'}, status=502)


class OpcoesViewSet(ScopedViewSet, mixins.ListModelMixin):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    permission_overrides = {'list': 'clientes.view_cliente'}

    def get_permissions(self):
        # Somente IDs e rótulos, necessários inclusive a operadores de liberações.
        return [IsAuthenticated()]

    def list(self, request, **kwargs):
        tipo = request.query_params.get('tipo', 'clientes')
        if tipo not in ('clientes', 'parceiros'):
            raise ValidationError({'tipo': 'Escolha clientes ou parceiros.'})
        permissions = ('clientes.view_cliente', 'clientes.add_cliente', 'clientes.change_cliente',
                       'clientes.view_parceiro', 'clientes.add_parceiro', 'clientes.change_parceiro',
                       'financeiro.add_recreceita', 'clientes.view_liberacaodatas',
                       'clientes.add_liberacaodatas', 'clientes.change_liberacaodatas')
        if not any(request.user.has_perm(p) for p in permissions):
            raise PermissionDenied('Sem permissão para consultar opções de cadastro.')
        model = Cliente if tipo == 'clientes' else Parceiro
        qs = self.scoped(model.objects.all()).order_by('instituicao', 'pk')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(instituicao__icontains=search)
        if request.query_params.get('id'):
            qs = qs.filter(pk=integer(request.query_params['id'], 'id'))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response([{'id': obj.pk, 'instituicao': obj.instituicao} for obj in page])


class BancoViewSet(ReferenciaViewSet):
    from conta.models import Banco
    queryset = Banco.objects.order_by('codigo', 'pk')
    serializer_class = BancoSerializer
