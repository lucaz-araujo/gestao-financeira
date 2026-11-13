from decimal import Decimal
from django.db import transaction, IntegrityError
from django.db.models import Q, Sum, Count, F
from django.db.models.deletion import ProtectedError
from django.utils.functional import cached_property
from rest_framework import viewsets, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from contabil.models import PlanoContas
from financeiro.models import FechamentoCaixa
from core.api import empresa_da_requisicao
from .models import Banco, Conta, Movimento, Transferencia
from .serializers import BancoSerializer, ContaSerializer, MovimentoSerializer, TransferenciaSerializer
from .services import ContaConflict, bloquear_contas, periodo_aberto, manual, validar_par, gravar_transferencia


class ContaPermission(BasePermission):
    def has_permission(self, request, view):
        operation = {'create': 'add', 'update': 'change', 'partial_update': 'change', 'destroy': 'delete'}.get(view.action, 'view')
        return request.user.has_perm(f'conta.{operation}_{view.queryset.model._meta.model_name}')


class Pagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


def interval(params):
    start, end = params.get('dt_inicial'), params.get('dt_final')
    if bool(start) != bool(end):
        raise ValidationError({'dt_final': 'Informe as duas datas do intervalo.'})
    if start:
        start, end = serializers.DateField().run_validation(start), serializers.DateField().run_validation(end)
        if start > end:
            raise ValidationError({'dt_final': 'A data final deve ser igual ou posterior à inicial.'})
    return start, end


class BaseViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated, ContaPermission)
    pagination_class = Pagination
    @cached_property
    def empresa_id(self):
        return empresa_da_requisicao(self.request)

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'empresa_id': self.empresa_id}

    def base_queryset(self):
        return self.queryset.filter(empresa_id=self.empresa_id)

    def get_queryset(self):
        qs = self.base_queryset()
        search = self.request.query_params.get('search')
        if search:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{field + '__icontains': search})
            qs = qs.filter(query)
        if self.action in ('update', 'partial_update', 'destroy'):
            qs = qs.select_for_update(of=('self',))
        return qs

    @transaction.atomic
    def create(self, *args, **kwargs):
        return super().create(*args, **kwargs)

    @transaction.atomic
    def update(self, *args, **kwargs):
        return super().update(*args, **kwargs)

    @transaction.atomic
    def destroy(self, *args, **kwargs):
        return super().destroy(*args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(empresa_id=self.empresa_id)

    def handle_exception(self, exc):
        if isinstance(exc, (ProtectedError, IntegrityError)):
            exc = ContaConflict('O registro possui vínculos ou um conflito de integridade. Os dados foram preservados.')
        return super().handle_exception(exc)


class BancoViewSet(BaseViewSet):
    queryset = Banco.objects.order_by('codigo', 'pk')
    serializer_class = BancoSerializer
    search_fields = ('codigo', 'nome')
    def base_queryset(self):
        self.empresa_id  # Mesmo catálogo global exige contexto autorizado da sessão.
        return self.queryset
    def perform_create(self, serializer):
        serializer.save()


class ContaViewSet(BaseViewSet):
    queryset = Conta.objects.select_related('banco', 'conta_contabil').order_by('descricao', 'pk')
    serializer_class = ContaSerializer
    search_fields = ('descricao', 'numeroconta', 'agencia', 'banco__nome')


class OperacaoViewSet(BaseViewSet):
    def get_queryset(self):
        qs = super().get_queryset()
        start, end = interval(self.request.query_params)
        if start:
            qs = qs.filter(dt_movimento__range=(start, end))
        for name in self.account_filters:
            if self.request.query_params.get(name):
                value = serializers.IntegerField(min_value=1).run_validation(self.request.query_params[name])
                qs = qs.filter(**{name + '_id': value})
        return qs


class MovimentoViewSet(OperacaoViewSet):
    queryset = Movimento.objects.select_related('conta', 'usuario').order_by('-dt_movimento', '-pk')
    serializer_class = MovimentoSerializer
    search_fields = ('nr_documento', 'historico', 'conta__descricao')
    account_filters = ('conta',)
    def base_queryset(self):
        return super().base_queryset().filter(conta__empresa_id=self.empresa_id)
    def get_queryset(self):
        qs = super().get_queryset()
        for name, choices in [('tipo_movimento', ('C', 'D')), ('tipo_documento', ('TED', 'DOC', 'CHE', 'TAR', 'OUT', 'DEP', 'TRA'))]:
            if self.request.query_params.get(name):
                qs = qs.filter(**{name: serializers.ChoiceField(choices=choices).run_validation(self.request.query_params[name])})
        return qs

    def perform_create(self, serializer):
        account, day = serializer.validated_data['conta'], serializer.validated_data['dt_movimento']
        bloquear_contas([account.pk], self.empresa_id)
        periodo_aberto([account.pk], day)
        serializer.save(empresa_id=self.empresa_id, usuario=self.request.user)

    def perform_update(self, serializer):
        old = serializer.instance
        manual(old)
        new_account = serializer.validated_data.get('conta', old.conta)
        day = serializer.validated_data.get('dt_movimento', old.dt_movimento)
        bloquear_contas([old.conta_id, new_account.pk], self.empresa_id)
        periodo_aberto([old.conta_id], old.dt_movimento)
        periodo_aberto([new_account.pk], day)
        serializer.save(usuario=self.request.user)

    def perform_destroy(self, instance):
        manual(instance)
        bloquear_contas([instance.conta_id], self.empresa_id)
        periodo_aberto([instance.conta_id], instance.dt_movimento)
        instance.delete()

    def report_response(self, qs, extra=None):
        sums = qs.aggregate(creditos=Sum('valor', filter=Q(tipo_movimento='C')), debitos=Sum('valor', filter=Q(tipo_movimento='D')))
        credits, debits = sums['creditos'] or Decimal('0'), sums['debitos'] or Decimal('0')
        response = self.get_paginated_response(self.get_serializer(self.paginate_queryset(qs), many=True).data)
        response.data.update(creditos=str(credits), debitos=str(debits), saldo_periodo=str(credits-debits), **(extra or {}))
        return response

    @action(detail=False, methods=['get'])
    def relatorio(self, request):
        return self.report_response(self.get_queryset())

    @action(detail=False, methods=['get'])
    def extrato(self, request):
        account = serializers.IntegerField(min_value=1).run_validation(request.query_params.get('conta'))
        start, end = interval(request.query_params)
        if not start:
            raise ValidationError({'dt_inicial': 'Informe um período para gerar o extrato.'})
        if not Conta.objects.filter(pk=account, empresa_id=self.empresa_id).exists():
            raise PermissionDenied('Conta fora da empresa selecionada.')
        base = self.base_queryset().filter(conta_id=account)
        closure = FechamentoCaixa.objects.filter(conta_id=account, empresa_id=self.empresa_id, data__lt=start).order_by('-data', '-pk').first()
        before = base.filter(dt_movimento__lt=start)
        opening = closure.saldo if closure else Decimal('0')
        if closure:
            before = before.filter(dt_movimento__gt=closure.data)
        totals = before.aggregate(c=Sum('valor', filter=Q(tipo_movimento='C')), d=Sum('valor', filter=Q(tipo_movimento='D')))
        opening += (totals['c'] or Decimal('0')) - (totals['d'] or Decimal('0'))
        response = self.report_response(base.filter(dt_movimento__range=(start, end)).order_by('dt_movimento', 'pk'), {'saldo_anterior': str(opening)})
        response.data['saldo_final'] = str(opening + Decimal(response.data['saldo_periodo']))
        return response


class TransferenciaViewSet(OperacaoViewSet):
    queryset = Transferencia.objects.select_related('conta_origem', 'conta_destino', 'usuario').prefetch_related('transferencia').order_by('-dt_movimento', '-pk')
    serializer_class = TransferenciaSerializer
    search_fields = ('nr_documento', 'historico', 'conta_origem__descricao', 'conta_destino__descricao')
    account_filters = ('conta_origem', 'conta_destino')
    def base_queryset(self):
        return super().base_queryset().filter(conta_origem__empresa_id=self.empresa_id, conta_destino__empresa_id=self.empresa_id)
    def get_queryset(self):
        qs = super().get_queryset()
        state = self.request.query_params.get('integridade')
        if state and self.action in ('list', 'relatorio'):
            serializers.ChoiceField(choices=['consistente', 'pendente']).run_validation(state)
            valid = Q(transferencia__empresa_id=F('empresa_id'), transferencia__valor=F('valor'),
                      transferencia__dt_movimento=F('dt_movimento'), transferencia__tipo_documento='TRA',
                      transferencia__receita__isnull=True, transferencia__despesa__isnull=True)
            qs = qs.annotate(_legs=Count('transferencia'),
                _debits=Count('transferencia', filter=valid & Q(transferencia__tipo_movimento='D', transferencia__conta_id=F('conta_origem_id'))),
                _credits=Count('transferencia', filter=valid & Q(transferencia__tipo_movimento='C', transferencia__conta_id=F('conta_destino_id'))))
            consistent = Q(_legs=2, _debits=1, _credits=1)
            qs = qs.filter(consistent if state == 'consistente' else ~consistent)
        return qs

    def perform_create(self, serializer):
        gravar_transferencia(serializer, self.request.user, self.empresa_id)
    def perform_update(self, serializer):
        gravar_transferencia(serializer, self.request.user, self.empresa_id)
    def perform_destroy(self, instance):
        bloquear_contas([instance.conta_origem_id, instance.conta_destino_id], self.empresa_id)
        periodo_aberto([instance.conta_origem_id, instance.conta_destino_id], instance.dt_movimento)
        legs = validar_par(instance)
        for leg in legs:
            leg.delete()
        instance.delete()
    @action(detail=False, methods=['get'])
    def relatorio(self, request):
        qs = self.get_queryset()
        total = qs.aggregate(total=Sum('valor'))['total'] or Decimal('0')
        response = self.get_paginated_response(self.get_serializer(self.paginate_queryset(qs), many=True).data)
        response.data['valor_total'] = str(total)
        return response


class OpcoesViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated,)
    pagination_class = Pagination
    def list(self, request):
        empresa = empresa_da_requisicao(request)
        kind = request.query_params.get('tipo', 'contas')
        permissions = {'bancos': [('conta', 'conta'), ('banco', 'conta')], 'planos': [('conta', 'conta')],
                       'contas': [('conta', 'conta'), ('movimento', 'conta'), ('transferencia', 'conta')]}
        if kind not in permissions:
            raise ValidationError({'tipo': 'Escolha bancos, contas ou planos.'})
        if not any(request.user.has_perm(f'{app}.{verb}_{model}') for model, app in permissions[kind] for verb in ('view', 'add', 'change')):
            raise PermissionDenied('Sem permissão para consultar estas opções.')
        if kind == 'bancos':
            qs, search_fields = Banco.objects.all(), ('nome', 'codigo')
        elif kind == 'planos':
            qs, search_fields = PlanoContas.objects.filter(empresa_id=empresa), ('conta', 'descricao')
        else:
            qs, search_fields = Conta.objects.filter(empresa_id=empresa), ('descricao', 'numeroconta')
        if request.query_params.get('id'):
            qs = qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
        if request.query_params.get('search'):
            query = Q()
            for field in search_fields:
                query |= Q(**{field+'__icontains': request.query_params['search']})
            qs = qs.filter(query)
        page = self.paginate_queryset(qs.order_by('pk'))
        return self.get_paginated_response([{'id': o.pk, 'descricao': str(o)} for o in page])
