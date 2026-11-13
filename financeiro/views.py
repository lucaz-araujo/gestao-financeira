"""API financeira: contexto obrigatório, permissões por ação e operações transacionais."""
import calendar
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError as ModelValidationError, PermissionDenied as ModelPermissionDenied
from django.db import transaction, DatabaseError
from django.db.models import Q, Sum, OuterRef, Subquery, DecimalField, Value, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from conta.models import Conta
from conta.services import ContaConflict
from conta.views import BaseViewSet, Pagination, interval
from core.api import empresa_da_requisicao
from clientes.models import Cliente
from compras.models import Fornecedor
from contabil.models import CentroCusto, TipoDespesa
from notas.models import Nota
from .models import DocReceita, DocDespesa, RecReceita, PagDespesa, FechamentoCaixa
from .serializers import (DocReceitaSerializer, DocDespesaSerializer, RecReceitaSerializer,
    PagDespesaSerializer, FechamentoSerializer, AnaliseSerializer, clientes_visiveis)
from .services import (total_documento, bloquear_documento, registrar_baixa, estornar_baixa,
    fechar_caixa, reabrir_caixa, analise_financeira)


class FinanceiroPermission(BasePermission):
    def has_permission(self, request, view):
        model = view.queryset.model._meta.model_name
        verb = {'create': 'add', 'update': 'change', 'partial_update': 'change', 'destroy': 'delete',
                'duplicar': 'add', 'reabrir': 'delete'}.get(view.action, 'view')
        if not request.user.has_perm(f'financeiro.{verb}_{model}'):
            return False
        if view.action in ('baixas', 'baixar', 'estornar', 'previsualizar', 'conciliar'):
            operation = 'view' if view.action == 'baixas' else 'delete' if view.action == 'estornar' else 'add'
            return request.user.has_perm(f'financeiro.{operation}_{view.baixa_model._meta.model_name}')
        return True


class FinancialBase(BaseViewSet):
    permission_classes = (IsAuthenticated, FinanceiroPermission)
    def handle_exception(self, exc):
        if isinstance(exc, ModelValidationError):
            exc = ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
        elif isinstance(exc, ModelPermissionDenied):
            exc = PermissionDenied(str(exc))
        elif isinstance(exc, DatabaseError):
            exc = ContaConflict('A operação não pôde ser concluída. Verifique os vínculos e os fechamentos; nenhum dado foi alterado.')
        return super().handle_exception(exc)


class DocumentoViewSet(FinancialBase):
    def base_queryset(self):
        qs = self.queryset.filter(empresa_id=self.empresa_id)
        if self.queryset.model == DocReceita:
            qs = qs.filter(cliente__in=clientes_visiveis(self.empresa_id, self.request.user))
        totals = self.baixa_model.objects.filter(**{self.parent_field + '_id': OuterRef('pk')}).order_by().values(self.parent_field).annotate(t=Sum('valor')).values('t')
        return qs.annotate(_total=Coalesce(Subquery(totals, output_field=DecimalField(max_digits=15, decimal_places=2)), Value(Decimal('0'))))

    def get_queryset(self):
        # Nota -> documento -> conta é a ordem única dos bloqueios de escrita.
        qs = self.base_queryset()
        if self.action not in ('list', 'relatorio'):
            return qs
        params = self.request.query_params
        if params.get('search'):
            query = Q()
            for field in self.search_fields:
                query |= Q(**{field+'__icontains': params['search']})
            qs = qs.filter(query)
        start, end = interval(params)
        if start:
            qs = qs.filter(dt_vencimento__range=(start, end))
        if params.get('situacao'):
            state = serializers.ChoiceField(choices=['aberto', 'quitado', 'vencido']).run_validation(params['situacao'])
            qs = qs.filter(_total__gte=F('valor')) if state == 'quitado' else qs.filter(_total__lt=F('valor'))
            if state == 'vencido':
                qs = qs.filter(dt_vencimento__lt=timezone.localdate())
        for field in ('cliente', 'nota') if self.parent_field == 'receita' else ('fornecedor', 'centro_custo', 'tipo_despesa'):
            if params.get(field):
                qs = qs.filter(**{field+'_id': serializers.IntegerField(min_value=1).run_validation(params[field])})
        paid_start, paid_end = interval({'dt_inicial': params.get('pagamento_inicial'), 'dt_final': params.get('pagamento_final')})
        if paid_start:
            ids = self.baixa_model.objects.filter(dt_pagamento__range=(paid_start, paid_end)).values(self.parent_field+'_id')
            qs = qs.filter(pk__in=ids)
        return qs

    def perform_create(self, serializer):
        if self.parent_field == 'receita':
            note = Nota.objects.select_for_update().get(pk=serializer.validated_data['nota'].pk)
            if note.operacoes.filter(estado__in=['executando', 'incerta']).exists() or note.cancelada_em:
                raise ContaConflict('Concilie o estado fiscal da nota antes de criar a receita.')
            if DocReceita.objects.filter(nota=note).exists():
                raise ContaConflict('Esta nota já possui documento financeiro. Use o documento existente.')
        serializer.save(empresa_id=self.empresa_id, user_registro=self.request.user, dt_registro=timezone.localdate())
        serializer.instance._total = Decimal('0')

    def perform_update(self, serializer):
        doc = bloquear_documento(serializer.instance)
        relation = doc.recebimento if self.parent_field == 'receita' else doc.pagamentos
        if relation.exists() or (doc.valor_recebido if self.parent_field == 'receita' else doc.valor_pago):
            raise ContaConflict('Documento com baixa: estorne e concilie os recebimentos/pagamentos antes de editar.')
        if self.parent_field == 'receita' and any(name in serializer.validated_data and serializer.validated_data[name].pk != getattr(doc, name+'_id') for name in ('nota', 'cliente')):
            raise ValidationError({'nota': 'Não é permitido trocar a nota ou o cliente de um documento existente.'})
        doc._total = Decimal('0')
        serializer.instance = doc
        serializer.save()

    def perform_destroy(self, instance):
        doc = bloquear_documento(instance)
        if total_documento(doc) or (doc.valor_recebido if self.parent_field == 'receita' else doc.valor_pago):
            raise ContaConflict('Documento com baixa: estorne e concilie antes de excluir.')
        doc.delete()

    @action(detail=True, methods=['get'])
    def baixas(self, request, pk=None):
        doc = self.get_object()
        qs = self.baixa_model.objects.filter(**{self.parent_field: doc}).select_related('conta', 'user_registro').order_by('-dt_pagamento', '-pk')
        return self.get_paginated_response(self.baixa_serializer(self.paginate_queryset(qs), many=True).data)

    @action(detail=True, methods=['post'])
    def baixar(self, request, pk=None):
        doc = self.get_object()
        serializer = self.baixa_serializer(data=request.data, context={**self.get_serializer_context(), 'documento': doc})
        serializer.is_valid(raise_exception=True)
        obj, created = registrar_baixa(doc, serializer.validated_data, request.user)
        return Response(self.baixa_serializer(obj).data, status=201 if created else 200)

    @action(detail=True, methods=['post'])
    def estornar(self, request, pk=None):
        registro = serializers.IntegerField(min_value=1).run_validation(request.data.get('baixa'))
        estornar_baixa(self.get_object(), registro)
        return Response({'detail': 'Baixa estornada e saldo recalculado. Liberações de acesso existentes foram preservadas.'})

    @action(detail=False, methods=['get'])
    def relatorio(self, request):
        qs = self.get_queryset()
        totals = qs.aggregate(valor_total=Sum('valor'), total_baixado=Sum('_total'))
        response = self.get_paginated_response(self.get_serializer(self.paginate_queryset(qs), many=True).data)
        response.data.update({key: str(value or Decimal('0')) for key, value in totals.items()})
        response.data['saldo_total'] = str((totals['valor_total'] or Decimal('0')) - (totals['total_baixado'] or Decimal('0')))
        return response


class ReceitaViewSet(DocumentoViewSet):
    queryset = DocReceita.objects.select_related('cliente', 'nota__contrato', 'user_registro').order_by('dt_vencimento', 'pk')
    serializer_class = DocReceitaSerializer
    baixa_model, baixa_serializer, parent_field = RecReceita, RecReceitaSerializer, 'receita'
    search_fields = ('numero', 'descricao', 'cliente__instituicao')

    @action(detail=False, methods=['post'])
    def previsualizar(self, request):
        from .conciliacao import previsualizar
        return Response(previsualizar(request.FILES.get('extrato'), self.empresa_id, request.user.pk))

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def conciliar(self, request):
        from .conciliacao import validar_linhas
        items = validar_linhas(request.data.get('itens'), self.empresa_id, request.user.pk)
        account = serializers.PrimaryKeyRelatedField(queryset=Conta.objects.filter(empresa_id=self.empresa_id)).run_validation(request.data.get('conta'))
        docs = {doc.pk: doc for doc in self.base_queryset().filter(pk__in=[item['receita'] for item in items])}
        if any(item['receita'] not in docs for item in items):
            raise PermissionDenied('Há documentos fora do seu escopo de acesso.')
        results = []
        for item in sorted(items, key=lambda item: (docs[item['receita']].nota_id, item['receita'])):
            doc = docs[item['receita']]
            data = {**item, 'conta': account.pk}
            serializer = RecReceitaSerializer(data=data, context={**self.get_serializer_context(), 'documento': doc})
            serializer.is_valid(raise_exception=True)
            obj, created = registrar_baixa(doc, serializer.validated_data, request.user)
            results.append({'receita': doc.pk, 'baixa': obj.pk, 'criada': created})
        return Response({'results': results})


class DespesaViewSet(DocumentoViewSet):
    queryset = DocDespesa.objects.select_related('fornecedor', 'centro_custo', 'tipo_despesa', 'user_registro').order_by('dt_vencimento', 'pk')
    serializer_class = DocDespesaSerializer
    baixa_model, baixa_serializer, parent_field = PagDespesa, PagDespesaSerializer, 'despesa'
    search_fields = ('numero', 'descricao', 'fornecedor__instituicao')

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def duplicar(self, request, pk=None):
        original = bloquear_documento(self.get_object())
        count = serializers.IntegerField(min_value=1, max_value=60).run_validation(request.data.get('quantidade'))
        start = serializers.DateField().run_validation(request.data.get('primeiro_vencimento'))
        ids = []
        for offset in range(count):
            year, month = divmod(start.year * 12 + start.month - 1 + offset, 12)
            due = date(year, month+1, min(start.day, calendar.monthrange(year, month+1)[1]))
            obj = DocDespesa(empresa_id=self.empresa_id, fornecedor=original.fornecedor, numero=original.numero,
                descricao=original.descricao, dt_vencimento=due, valor=original.valor, valor_pago=0, situacao='A',
                tipo_despesa=original.tipo_despesa, centro_custo=original.centro_custo,
                dt_registro=timezone.localdate(), user_registro=request.user)
            obj.clean(); obj.save(); ids.append(obj.pk)
        return Response({'ids': ids, 'detail': f'{count} despesas criadas.'}, status=201)


class FechamentoViewSet(FinancialBase):
    queryset = FechamentoCaixa.objects.select_related('conta', 'user_fechamento').order_by('-data', '-pk')
    serializer_class = FechamentoSerializer
    search_fields = ('conta__descricao',)
    http_method_names = ['get', 'post', 'head', 'options']
    def get_queryset(self):
        qs = self.base_queryset().filter(conta__empresa_id=self.empresa_id)
        start, end = interval(self.request.query_params)
        if start:
            qs = qs.filter(data__range=(start, end))
        if self.request.query_params.get('conta'):
            qs = qs.filter(conta_id=serializers.IntegerField(min_value=1).run_validation(self.request.query_params['conta']))
        return qs
    def create(self, request, *args, **kwargs):
        account = serializers.PrimaryKeyRelatedField(queryset=Conta.objects.filter(empresa_id=self.empresa_id)).run_validation(request.data.get('conta'))
        start, end = interval(request.data)
        if not start:
            raise ValidationError({'dt_inicial': 'Informe o período de fechamento.'})
        result = fechar_caixa(request.user, self.empresa_id, account.pk, start, end)
        return Response({'detail': result}, status=201)
    @action(detail=True, methods=['post'])
    def reabrir(self, request, pk=None):
        reabrir_caixa(request.user, self.empresa_id, self.get_object().pk)
        return Response({'detail': 'Último fechamento reaberto.'})
    @action(detail=False, methods=['get'])
    def analise(self, request):
        if not all(request.user.has_perm('financeiro.view_'+m) for m in ('docreceita', 'docdespesa')):
            raise PermissionDenied('A análise exige acesso às receitas e despesas.')
        if request.user.uf_id:
            raise PermissionDenied('A análise consolidada exige acesso financeiro sem restrição de UF.')
        start, end = interval(request.query_params)
        rows, totals = analise_financeira(request.user, self.empresa_id, start, end)
        return Response({'results': AnaliseSerializer(rows, many=True).data, 'totais': {key: str(value) for key, value in totals.items()}})


class OpcoesViewSet(viewsets.GenericViewSet):
    authentication_classes = FinancialBase.authentication_classes
    permission_classes = (IsAuthenticated,)
    pagination_class = Pagination
    def list(self, request):
        company = empresa_da_requisicao(request)
        kind = request.query_params.get('tipo')
        access = {'clientes': ['docreceita'], 'notas': ['docreceita'], 'fornecedores': ['docdespesa'],
                  'centros': ['docdespesa'], 'tipos': ['docdespesa'], 'contas': ['recreceita', 'pagdespesa', 'fechamentocaixa'], 'receitas': ['recreceita']}
        if kind not in access:
            raise ValidationError({'tipo': 'Tipo de opção inválido.'})
        if not any(request.user.has_perm(f'financeiro.{verb}_{model}') for model in access[kind] for verb in ('view', 'add', 'change')):
            raise PermissionDenied('Sem permissão para consultar estas opções.')
        customers = clientes_visiveis(company, request.user)
        if kind == 'clientes':
            qs, fields = customers, ['instituicao']
        elif kind == 'notas':
            qs, fields = Nota.objects.filter(empresa_id=company, contrato__cliente__in=customers, cancelada_em__isnull=True), ['numero', 'texto_nota']
            if request.query_params.get('cliente'):
                qs = qs.filter(contrato__cliente_id=serializers.IntegerField(min_value=1).run_validation(request.query_params['cliente']))
        elif kind == 'fornecedores':
            qs, fields = Fornecedor.objects.filter(empresa_id=company), ['instituicao']
        elif kind == 'centros':
            qs, fields = CentroCusto.objects.filter(empresa_id=company), ['descricao', 'codigo']
        elif kind == 'tipos':
            qs, fields = TipoDespesa.objects.filter(Q(conta__isnull=True) | Q(conta__empresa_id=company)), ['descricao', 'codigo']
        elif kind == 'receitas':
            if not request.user.has_perm('financeiro.view_docreceita'):
                raise PermissionDenied('Sem permissão para consultar receitas.')
            qs, fields = DocReceita.objects.filter(empresa_id=company, cliente__in=customers), ['numero', 'cliente__instituicao']
        else:
            qs, fields = Conta.objects.filter(empresa_id=company), ['descricao', 'numeroconta']
        if request.query_params.get('id'):
            qs = qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
        if request.query_params.get('search'):
            query = Q()
            for field in fields:
                query |= Q(**{field+'__icontains': request.query_params['search']})
            qs = qs.filter(query)
        page = self.paginate_queryset(qs.order_by('pk'))
        return self.get_paginated_response([{'id': obj.pk, 'descricao': str(obj)} for obj in page])
