from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction, IntegrityError
from django.db.models import Exists, OuterRef, Q, Sum
from django.db.models.deletion import ProtectedError
from django.utils.functional import cached_property
from rest_framework import serializers, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from clientes.models import Cliente, Parceiro
from core.api import empresa_da_requisicao
from notas.models import Nota
from produtos.models import Produto
from .models import Contrato
from .serializers import ContratoSerializer, ContratoResumoSerializer, ContratoRelatorioSerializer, CalculoContratoSerializer


class ContratoConflict(APIException):
    status_code = 409
    default_code = 'conflict'
    default_detail = 'Operação impedida: existem notas ou outros registros vinculados ao contrato.'


class ContratoPermission(BasePermission):
    def has_permission(self, request, view):
        operation = {'create': 'add', 'update': 'change', 'partial_update': 'change', 'destroy': 'delete'}.get(view.action, 'view')
        if view.action in ('opcoes', 'calcular'):
            return any(request.user.has_perm('contratos.' + p + '_contrato') for p in ('view', 'add', 'change'))
        return request.user.has_perm(f'contratos.{operation}_contrato')


class ContratoPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class ContratoViewSet(viewsets.ModelViewSet):
    queryset = Contrato.objects.all()
    authentication_classes = (JWTAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated, ContratoPermission)
    pagination_class = ContratoPagination

    @cached_property
    def empresa_id(self):
        return empresa_da_requisicao(self.request)

    def get_queryset(self):
        qs = super().get_queryset().filter(empresa_id=self.empresa_id, cliente__empresa_id=self.empresa_id)
        if self.request.user.uf_id:
            qs = qs.filter(cliente__uf_id=self.request.user.uf_id)
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(numero__icontains=search) | Q(cliente__instituicao__icontains=search))
        for parameter, field in (('cliente', 'cliente_id'), ('parceiro', 'cliente__parceiro_id'), ('uf', 'cliente__uf_id')):
            values = self.request.query_params.getlist(parameter)
            if values:
                try:
                    ids = [int(value) for part in values for value in part.split(',')]
                    if any(pk < 1 for pk in ids):
                        raise ValueError
                except ValueError:
                    raise ValidationError({parameter: 'Informe IDs válidos.'})
                qs = qs.filter(**{field + '__in': ids})
        if 'ativo' in self.request.query_params:
            active = serializers.BooleanField().run_validation(self.request.query_params['ativo'])
            qs = qs.filter(ativo=active)
        start, end = self.request.query_params.get('dt_inicial'), self.request.query_params.get('dt_final')
        if start or end:
            if not start or not end:
                raise ValidationError({'dt_final': 'Informe o início e o fim do intervalo de vencimento.'})
            start = serializers.DateField().run_validation(start)
            end = serializers.DateField().run_validation(end)
            if start > end:
                raise ValidationError({'dt_final': 'A data final deve ser igual ou posterior à inicial.'})
            qs = qs.filter(dt_data_final__range=(start, end))
        qs = qs.select_related('cliente__uf').annotate(possui_nota=Exists(Nota.objects.filter(contrato_id=OuterRef('pk'))))
        if self.action == 'relatorio':
            qs = qs.prefetch_related('produtosCont__produtos')
        elif self.action != 'list':
            qs = qs.prefetch_related('produtosCont__produtos', 'renovacao', 'ContNotas')
        if self.action in ('update', 'partial_update', 'destroy'):
            qs = qs.select_for_update(of=('self',))
        return qs.order_by('cliente__instituicao', 'numero', 'pk')

    def get_serializer_class(self):
        if self.action == 'list':
            return ContratoResumoSerializer
        if self.action == 'relatorio':
            return ContratoRelatorioSerializer
        return ContratoSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'empresa_id': self.empresa_id}

    def perform_create(self, serializer):
        serializer.save(empresa_id=self.empresa_id)

    @transaction.atomic
    def update(self, *args, **kwargs):
        return super().update(*args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Consulta nova sob lock; nunca apaga notas, recebimentos ou documentos fiscais.
        if Nota.objects.filter(contrato_id=instance.pk).exists():
            raise ContratoConflict()
        instance.produtosCont.all().delete()
        instance.renovacao.all().delete()
        instance.delete()
        return Response(status=204)

    def handle_exception(self, exc):
        if isinstance(exc, ProtectedError):
            exc = ContratoConflict()
        elif isinstance(exc, IntegrityError):
            exc = ContratoConflict('Não foi possível gravar: há um conflito de integridade.')
        return super().handle_exception(exc)

    @action(detail=False, methods=['get'])
    def relatorio(self, request):
        if request.query_params.get('tipo_relatorio', 'S') not in ('S', 'C'):
            raise ValidationError({'tipo_relatorio': 'Escolha S (Simplificado) ou C (Com produtos).'})
        qs = self.get_queryset().filter(cliente__desativar=False)
        total = qs.aggregate(total=Sum('valor_liquido'))['total'] or Decimal('0')
        page = self.paginate_queryset(qs)
        response = self.get_paginated_response(self.get_serializer(page, many=True).data)
        response.data['valor_total'] = str(total.quantize(Decimal('0.01')))
        return response

    @action(detail=False, methods=['post'])
    def calcular(self, request):
        self.empresa_id  # Exige contexto de empresa mesmo sem gravar.
        serializer = CalculoContratoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        values = {name: (data['valor_bruto'] * data['perc_' + name] / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) for name in ('iss', 'irpj')}
        return Response({'valor_iss': str(values['iss']), 'valor_irpj': str(values['irpj']),
                         'valor_liquido': str(data['valor_bruto'] - values['iss'] - values['irpj'])})

    @action(detail=False, methods=['get'])
    def opcoes(self, request):
        kind = request.query_params.get('tipo', 'clientes')
        if kind not in ('clientes', 'parceiros', 'produtos'):
            raise ValidationError({'tipo': 'Escolha clientes, parceiros ou produtos.'})
        model = {'clientes': Cliente, 'parceiros': Parceiro, 'produtos': Produto}[kind]
        field = 'descricao' if kind == 'produtos' else 'instituicao'
        qs = model.objects.filter(empresa_id=self.empresa_id)
        if kind != 'produtos' and request.user.uf_id:
            qs = qs.filter(uf_id=request.user.uf_id)
        if request.query_params.get('id'):
            pk = serializers.IntegerField(min_value=1).run_validation(request.query_params['id'])
            qs = qs.filter(pk=pk)
        if request.query_params.get('search'):
            qs = qs.filter(**{field + '__icontains': request.query_params['search']})
        page = self.paginate_queryset(qs.order_by(field, 'pk'))
        return self.get_paginated_response([{'id': obj.pk, field: getattr(obj, field)} for obj in page])
