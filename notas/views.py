from decimal import Decimal
from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, Exists, OuterRef
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.functional import cached_property
from rest_framework import serializers, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from contratos.models import Contrato
from clientes.models import Cliente
from core.api import empresa_da_requisicao
from .models import Nota, OperacaoFiscal
from .serializers import NotaSerializer, OperacaoFiscalSerializer, GeracaoNotasSerializer, AcaoFiscalSerializer
from .services import NotaConflict, execute_operation, gerar_rascunhos, gerar_receita
from .gateway import fiscal_status
from .mailing import email_status, public_path, SALT


class NotaPermission(BasePermission):
    def has_permission(self, request, view):
        if view.action in ('opcoes', 'configuracao'):
            return any(request.user.has_perm('notas.' + action + '_nota') for action in ('view', 'add', 'change'))
        if view.action == 'financeiro':
            return request.user.has_perm('financeiro.add_docreceita')
        if view.action in ('create', 'gerar'):
            permission = 'notas.add_nota'
        elif view.action == 'destroy':
            permission = 'notas.delete_nota'
        elif view.action in ('update', 'partial_update', 'emitir', 'consultar', 'cancelar', 'email', 'email_cliente'):
            permission = 'notas.change_nota'
        else:
            permission = 'notas.view_nota'
        return request.user.has_perm(permission)


class NotaPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class NotaViewSet(viewsets.ModelViewSet):
    queryset = Nota.objects.all()
    serializer_class = NotaSerializer
    authentication_classes = (JWTAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated, NotaPermission)
    pagination_class = NotaPagination

    @cached_property
    def empresa_id(self):
        return empresa_da_requisicao(self.request)

    def get_queryset(self):
        qs = super().get_queryset().filter(empresa_id=self.empresa_id, contrato__empresa_id=self.empresa_id,
                                          contrato__cliente__empresa_id=self.empresa_id)
        if self.request.user.uf_id:
            qs = qs.filter(contrato__cliente__uf_id=self.request.user.uf_id)
        search = self.request.query_params.get('search', '')
        if search:
            qs = qs.filter(Q(numero__icontains=search) | Q(contrato__cliente__instituicao__icontains=search) | Q(contrato__numero__icontains=search))
        for parameter, field in (('cliente', 'contrato__cliente_id'), ('contrato', 'contrato_id'), ('uf', 'contrato__cliente__uf_id')):
            values = self.request.query_params.getlist(parameter)
            if values:
                try:
                    ids = [int(value) for part in values for value in part.split(',')]
                    if any(pk < 1 for pk in ids): raise ValueError
                except ValueError:
                    raise ValidationError({parameter: 'Informe IDs válidos.'})
                qs = qs.filter(**{field + '__in': ids})
        for field, minimum, maximum in (('competencia', 1, 12), ('exercicio', 1, 9999)):
            if field in self.request.query_params:
                value = serializers.IntegerField(min_value=minimum, max_value=maximum).run_validation(self.request.query_params[field])
                qs = qs.filter(**{field: value})
        if 'email_enviado' in self.request.query_params:
            qs = qs.filter(ja_enviou=serializers.BooleanField().run_validation(self.request.query_params['email_enviado']))
        paid = serializers.BooleanField().run_validation(self.request.query_params.get('pagas', False))
        if paid:
            qs = qs.filter(dt_data_pagamento__isnull=False)
        start, end = self.request.query_params.get('dt_inicial'), self.request.query_params.get('dt_final')
        if start or end:
            if not start or not end:
                raise ValidationError({'dt_final': 'Informe as datas inicial e final.'})
            start, end = serializers.DateField().run_validation(start), serializers.DateField().run_validation(end)
            if start > end:
                raise ValidationError({'dt_final': 'A data final deve ser igual ou posterior à inicial.'})
            qs = qs.filter(**{('dt_data_pagamento__range' if paid else 'dt_data_emissao__date__range'): (start, end)})
        state = self.request.query_params.get('estado')
        if state:
            uncertain = Exists(OperacaoFiscal.objects.filter(nota_id=OuterRef('pk'), estado='incerta'))
            pending = Exists(OperacaoFiscal.objects.filter(nota_id=OuterRef('pk'), estado='executando'))
            qs = qs.annotate(_uncertain=uncertain, _pending=pending, _has_emission=Exists(OperacaoFiscal.objects.filter(nota_id=OuterRef('pk'), acao='emitir')))
            authorized = Q(protocolo_recebimento__isnull=False) & ~Q(protocolo_recebimento='')
            sent = (Q(protocolo_envio__isnull=False) & ~Q(protocolo_envio='')) | Q(ja_enviou_NFSE=True)
            unknown = Q(_uncertain=True) | (Q(_pending=False, _has_emission=False) & ~authorized & ~sent & (Q(numero_rps__isnull=False) | Q(numero_lote__isnull=False)))
            if state == 'cancelada':
                qs = qs.filter(cancelada_em__isnull=False)
            else:
                qs = qs.filter(cancelada_em__isnull=True)
                if state == 'incerta': qs = qs.filter(unknown)
                elif state == 'processando': qs = qs.filter(~unknown, _pending=True)
                elif state == 'autorizada': qs = qs.filter(authorized & ~unknown, _pending=False)
                elif state == 'enviada': qs = qs.filter(~authorized & sent & ~unknown, _pending=False)
                elif state == 'rascunho': qs = qs.filter(~authorized & ~sent & ~unknown, _pending=False)
                else: raise ValidationError({'estado': 'Estado fiscal inválido.'})
        qs = qs.select_related('contrato__cliente', 'cidade', 'uf').prefetch_related('operacoes', 'docreceitas')
        if self.action in ('update', 'partial_update', 'destroy'):
            qs = qs.select_for_update(of=('self',))
        return qs.order_by('-dt_data_emissao', '-pk')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'empresa_id': self.empresa_id}

    def perform_create(self, serializer):
        serializer.save(empresa_id=self.empresa_id)

    @transaction.atomic
    def update(self, *args, **kwargs):
        return super().update(*args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        nota = self.get_object()
        if nota.estado_fiscal != 'rascunho' or nota.docreceitas.exists() or nota.dt_data_pagamento or nota.operacoes.exists():
            raise NotaConflict('Somente rascunhos sem financeiro ou histórico de operações podem ser excluídos.')
        nota.delete()
        return Response(status=204)

    def handle_exception(self, exc):
        if isinstance(exc, (ProtectedError, IntegrityError)):
            exc = NotaConflict('Há vínculos ou um conflito de integridade que impedem a operação.')
        return super().handle_exception(exc)

    @action(detail=False, methods=['get'])
    def configuracao(self, request):
        return Response({**fiscal_status(self.empresa_id), 'email_disponivel': email_status()})

    @action(detail=False, methods=['get'])
    def opcoes(self, request):
        if request.query_params.get('tipo') == 'clientes':
            qs = Cliente.objects.filter(empresa_id=self.empresa_id)
            if request.user.uf_id: qs = qs.filter(uf_id=request.user.uf_id)
            if request.query_params.get('id'): qs = qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
            if request.query_params.get('search'): qs = qs.filter(instituicao__icontains=request.query_params['search'])
            page = self.paginate_queryset(qs.order_by('instituicao', 'pk'))
            return self.get_paginated_response([{'id': c.pk, 'instituicao': c.instituicao} for c in page])
        qs = Contrato.objects.filter(empresa_id=self.empresa_id, cliente__empresa_id=self.empresa_id).select_related('cliente')
        if request.user.uf_id: qs = qs.filter(cliente__uf_id=request.user.uf_id)
        if request.query_params.get('id'):
            qs = qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
        if request.query_params.get('search'):
            qs = qs.filter(Q(numero__icontains=request.query_params['search']) | Q(cliente__instituicao__icontains=request.query_params['search']))
        page = self.paginate_queryset(qs.order_by('cliente__instituicao', 'pk'))
        return self.get_paginated_response([{'id': c.pk, 'descricao': f'{c.numero or "Sem número"} — {c.cliente.instituicao}'} for c in page])

    @action(detail=False, methods=['post'])
    def gerar(self, request):
        serializer = GeracaoNotasSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        qs = Contrato.objects.filter(pk__in=data['contratos'], empresa_id=self.empresa_id, cliente__empresa_id=self.empresa_id)
        if request.user.uf_id: qs = qs.filter(cliente__uf_id=request.user.uf_id)
        contracts = list(qs)
        if len(contracts) != len(data['contratos']):
            raise ValidationError({'contratos': 'Há contratos inexistentes ou fora do seu escopo.'})
        generated = gerar_rascunhos(contracts, data['competencia'], data['exercicio'], data['decimo_terceiro'])
        return Response({'results': [{**self.get_serializer(nota).data, 'criada': criada} for nota, criada in generated]}, status=201)

    def _external(self, request, acao):
        nota = self.get_object()
        body = AcaoFiscalSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        op = execute_operation(nota.pk, request.user, acao, key=request.headers.get('Idempotency-Key'),
                               justificativa=body.validated_data.get('justificativa', ''))
        code = {'executando': 409, 'incerta': 502, 'falha': 400, 'concluida': 200}[op.estado]
        return Response({'operacao': OperacaoFiscalSerializer(op).data}, status=code)

    @action(detail=True, methods=['post'])
    def emitir(self, request, **kwargs): return self._external(request, 'emitir')

    @action(detail=True, methods=['post'])
    def consultar(self, request, **kwargs): return self._external(request, 'consultar')

    @action(detail=True, methods=['post'])
    def consultar_lote(self, request, **kwargs): return self._external(request, 'consultar_lote')

    @action(detail=True, methods=['post'])
    def cancelar(self, request, **kwargs): return self._external(request, 'cancelar')

    @action(detail=True, methods=['post'])
    def email(self, request, **kwargs): return self._external(request, 'email')

    @action(detail=True, methods=['post'])
    def email_cliente(self, request, **kwargs): return self._external(request, 'email_cliente')

    @action(detail=True, methods=['post'])
    def financeiro(self, request, **kwargs):
        nota = self.get_object()
        receipt, created = gerar_receita(nota.pk, request.user.pk)
        return Response({'id': receipt.pk, 'criada': created}, status=201 if created else 200)

    @action(detail=True, methods=['get'])
    def historico(self, request, **kwargs):
        nota = self.get_object()
        page = self.paginate_queryset(nota.operacoes.select_related('usuario').all())
        return self.get_paginated_response(OperacaoFiscalSerializer(page, many=True).data)

    @action(detail=True, methods=['get'])
    def link_publico(self, request, **kwargs):
        nota = self.get_object()
        if not nota.protocolo_recebimento:
            raise NotaConflict('A nota ainda não possui autorização fiscal.')
        path = public_path(nota, client_list=request.query_params.get('cliente') == 'true')
        return Response({'url': settings.PUBLIC_APP_URL + path if settings.PUBLIC_APP_URL else request.build_absolute_uri(path),
                         'validade_segundos': settings.NOTAS_PUBLIC_LINK_MAX_AGE})

    @action(detail=False, methods=['get'])
    def relatorio(self, request):
        qs = self.get_queryset()
        totals = qs.aggregate(total=Sum('valor_liquido'), imposto=Sum('imposto'))
        page = self.paginate_queryset(qs)
        response = self.get_paginated_response(self.get_serializer(page, many=True).data)
        response.data.update(valor_total=str(totals['total'] or Decimal('0')), total_imposto=str(totals['imposto'] or Decimal('0')))
        return response


def portal_publico(request, token):
    if request.method != 'GET':
        return HttpResponse(status=405)
    try:
        data = signing.loads(token, salt=SALT, max_age=settings.NOTAS_PUBLIC_LINK_MAX_AGE)
        qs = Nota.objects.filter(empresa_id=data['empresa'], contrato__empresa_id=data['empresa'],
                                 contrato__cliente_id=data['cliente'], contrato__cliente__empresa_id=data['empresa'])
        qs = qs.exclude(protocolo_recebimento__isnull=True).exclude(protocolo_recebimento='').select_related('empresa', 'contrato__cliente', 'cidade', 'uf')
        if 'nota' in data:
            nota = qs.get(pk=data['nota'])
            response = render(request, 'nota_publica.html', {'nota': nota})
        else:
            # Lista pública limitada aos documentos deste cliente e a links com validade curta.
            response = render(request, 'notas_cliente_publicas.html', {'notas': [(n, public_path(n)) for n in qs.order_by('-dt_data_emissao')[:500]]})
    except (signing.BadSignature, signing.SignatureExpired, Nota.DoesNotExist, KeyError, TypeError, ValueError):
        response = HttpResponse('Este link é inválido ou expirou. Solicite um novo link à empresa emissora.', status=410)
    response['Cache-Control'] = 'private, no-store'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


def link_legado(request, **kwargs):
    return HttpResponse('Este link antigo foi desativado. Solicite um novo link de acesso à empresa emissora.', status=410)
