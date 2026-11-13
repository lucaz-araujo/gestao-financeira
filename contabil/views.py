from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError
from conta.views import BaseViewSet
from conta.services import ContaConflict
from .models import PlanoContas, CentroCusto, TipoDespesa, Lancamentos
from .serializers import PlanoSerializer, CentroSerializer, TipoSerializer, LancamentoSerializer
from rest_framework.permissions import BasePermission, IsAuthenticated


class AccountingPermission(BasePermission):
    def has_permission(self, request, view):
        verb = {'create':'add','update':'change','partial_update':'change','destroy':'delete'}.get(view.action,'view')
        return request.user.has_perm(f'contabil.{verb}_{view.queryset.model._meta.model_name}')


class AccountingViewSet(BaseViewSet):
    permission_classes = (IsAuthenticated, AccountingPermission)
    def check_unique(self, serializer):
        # Serializa cadastros da empresa para evitar duplicatas por requisições concorrentes.
        from empresa.models import Empresa
        Empresa.objects.select_for_update().get(pk=self.empresa_id)
        old = serializer.instance
        for field in self.unique_fields:
            value = serializer.validated_data.get(field, getattr(old, field, None))
            if value and self.base_queryset().filter(**{field+'__iexact':value}).exclude(pk=old.pk if old else None).exists():
                raise ValidationError({field:'Este valor já está cadastrado neste contexto.'})
    def perform_create(self, serializer):
        self.check_unique(serializer)
        serializer.save(empresa_id=self.empresa_id)
    def perform_update(self, serializer):
        self.check_unique(serializer)
        serializer.save()


class PlanoViewSet(AccountingViewSet):
    queryset = PlanoContas.objects.order_by('conta','pk')
    serializer_class = PlanoSerializer
    search_fields = ('conta','descricao','codigo')
    unique_fields = ('conta','codigo')


class CentroViewSet(AccountingViewSet):
    queryset = CentroCusto.objects.select_related('conta').order_by('descricao','pk')
    serializer_class = CentroSerializer
    search_fields = ('codigo','descricao')
    unique_fields = ('codigo','descricao')


class TipoViewSet(AccountingViewSet):
    queryset = TipoDespesa.objects.select_related('conta').order_by('codigo','pk')
    serializer_class = TipoSerializer
    search_fields = ('codigo','descricao')
    unique_fields = ('codigo','descricao')
    def base_queryset(self):
        return self.queryset.filter(Q(conta__empresa_id=self.empresa_id)|Q(conta__isnull=True))
    def writable(self, obj):
        if not obj.conta_id:
            raise ContaConflict('Tipo compartilhado legado: somente consulta. Cadastre um tipo vinculado ao plano da empresa.')
        from financeiro.models import DocDespesa
        from compras.models import Solicitacao
        if DocDespesa.objects.filter(tipo_despesa=obj).exclude(empresa_id=self.empresa_id).exists() or Solicitacao.objects.filter(tipo_despesa=obj).exclude(empresa_id=self.empresa_id).exists():
            raise ContaConflict('Este tipo possui vínculos com outras empresas. Concilie antes de alterar.')
    def perform_create(self, serializer):
        self.check_unique(serializer); serializer.save()
    def perform_update(self, serializer):
        self.writable(serializer.instance)
        if 'conta' in serializer.validated_data and serializer.validated_data['conta'].pk != serializer.instance.conta_id:
            raise ValidationError({'conta':'O plano de um tipo existente não pode ser trocado.'})
        super().perform_update(serializer)
    def perform_destroy(self, instance):
        self.writable(instance); instance.delete()


class LancamentoViewSet(AccountingViewSet):
    queryset = Lancamentos.objects.select_related('conta_origem','conta_destino').order_by('-dt_data','-pk')
    serializer_class = LancamentoSerializer
    search_fields = ('descricao','conta_origem__descricao','conta_destino__descricao')
    unique_fields = ()
    def base_queryset(self):
        return self.queryset.filter(conta_origem__empresa_id=self.empresa_id,conta_destino__empresa_id=self.empresa_id)
    def perform_create(self, serializer):
        serializer.save()


class OpcoesViewSet(BaseViewSet):
    queryset = PlanoContas.objects.order_by('conta','pk')
    serializer_class = PlanoSerializer
    permission_classes = (IsAuthenticated,)
    search_fields = ('conta','descricao')
    http_method_names = ['get','head','options']
    def list(self, request):
        if not any(request.user.has_perm(f'contabil.{verb}_{model}') for model in ('planocontas','centrocusto','tipodespesa','lancamentos') for verb in ('view','add','change')):
            raise PermissionDenied('Sem permissão para consultar planos.')
        qs = self.get_queryset()
        if request.query_params.get('id'):
            from rest_framework import serializers
            qs = qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
        return self.get_paginated_response([{'id':obj.pk,'descricao':str(obj)} for obj in self.paginate_queryset(qs)])
    def retrieve(self, request, *args, **kwargs):
        raise PermissionDenied('Use a consulta de opções.')
