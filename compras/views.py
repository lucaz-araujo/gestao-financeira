from django.db import transaction
from django.db.models import Q
from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from conta.views import BaseViewSet, Pagination
from conta.services import ContaConflict
from core.api import empresa_da_requisicao
from contabil.models import CentroCusto, TipoDespesa
from clientes.models import Municipio, Uf
from conta.models import Banco
from .models import Fornecedor, Unidade, Itens, Solicitacao, Orcamento
from .serializers import FornecedorSerializer, UnidadeSerializer, ItemSerializer, SolicitacaoSerializer, OrcamentoSerializer
from .services import bloquear_solicitacao, estado_editavel, mudar_estado, finalizar


def solicitacoes_visiveis(user,company):
    qs = Solicitacao.objects.filter(empresa_id=company)
    if not (user.has_perm('compras.autorizar_solicitacao') or user.has_perm('compras.finalizar_solicitacao')):
        qs = qs.filter(user_solicitante=user)
    return qs


class CompraPermission(BasePermission):
    def has_permission(self,request,view):
        verb={'create':'add','update':'change','partial_update':'change','destroy':'delete','estado':'change','finalizar':'change'}.get(view.action,'view')
        if not request.user.has_perm(f'compras.{verb}_{view.queryset.model._meta.model_name}'): return False
        return view.action!='finalizar' or request.user.has_perm('compras.finalizar_solicitacao')


class CompraViewSet(BaseViewSet):
    permission_classes=(IsAuthenticated,CompraPermission)
    def get_queryset(self):
        qs=self.base_queryset()
        if self.action=='list' and self.request.query_params.get('search'):
            query=Q()
            for field in self.search_fields: query|=Q(**{field+'__icontains':self.request.query_params['search']})
            qs=qs.filter(query)
        return qs
    def unique(self,serializer,fields):
        from empresa.models import Empresa
        Empresa.objects.select_for_update().get(pk=self.empresa_id)
        for field in fields:
            value=serializer.validated_data.get(field,getattr(serializer.instance,field,None))
            if value and self.base_queryset().filter(**{field+'__iexact':value}).exclude(pk=serializer.instance.pk if serializer.instance else None).exists():
                raise ValidationError({field:'Valor já cadastrado nesta empresa.'})
    def perform_update(self,serializer):
        serializer.instance=self.queryset.select_for_update(of=('self',)).get(pk=serializer.instance.pk)
        serializer.save()


class FornecedorViewSet(CompraViewSet):
    queryset=Fornecedor.objects.select_related('cidade','uf').order_by('instituicao','pk')
    serializer_class=FornecedorSerializer
    search_fields=('instituicao','cnpj','cpf')


class UnidadeViewSet(CompraViewSet):
    queryset=Unidade.objects.order_by('descricao','pk')
    serializer_class=UnidadeSerializer
    search_fields=('descricao','sigla')
    def perform_create(self,serializer):
        self.unique(serializer,['descricao','sigla']);super().perform_create(serializer)
    def perform_update(self,serializer):
        self.unique(serializer,['descricao','sigla']);super().perform_update(serializer)


class ItemViewSet(CompraViewSet):
    queryset=Itens.objects.select_related('unidade').order_by('descricao','pk')
    serializer_class=ItemSerializer
    search_fields=('descricao','unidade__sigla')
    def perform_create(self,serializer):
        self.unique(serializer,['descricao']);super().perform_create(serializer)
    def perform_update(self,serializer):
        self.unique(serializer,['descricao']);super().perform_update(serializer)


class SolicitacaoViewSet(CompraViewSet):
    queryset=Solicitacao.objects.select_related('user_solicitante','user_autorizacao').prefetch_related('solicitacaoitem_set__item').order_by('-dt_solicitacao','-pk')
    serializer_class=SolicitacaoSerializer
    search_fields=('descricao',)
    def base_queryset(self):
        return self.queryset.filter(pk__in=solicitacoes_visiveis(self.request.user,self.empresa_id))
    def get_queryset(self):
        qs=super().get_queryset()
        if self.action=='list' and self.request.query_params.get('status'):
            qs=qs.filter(status=serializers.ChoiceField(choices=['AB','PE','AU','FI','CA']).run_validation(self.request.query_params['status']))
        return qs
    def perform_create(self,serializer):
        serializer.save(empresa_id=self.empresa_id,user_solicitante=self.request.user,status='AB')
    def perform_update(self,serializer):
        obj=bloquear_solicitacao(serializer.instance.pk);estado_editavel(obj,{'AB'})
        if obj.orcamentos_list.exists(): raise ContaConflict('Solicitação com orçamentos: itens e cabeçalho estão bloqueados.')
        serializer.instance=obj;serializer.save()
    def perform_destroy(self,instance):
        obj=bloquear_solicitacao(instance.pk);estado_editavel(obj,{'AB'})
        if obj.orcamentos_list.exists(): raise ContaConflict('Exclua os orçamentos antes de excluir a solicitação.')
        obj.solicitacaoitem_set.all().delete();obj.delete()
    @action(detail=True,methods=['post'])
    def estado(self,request,pk=None):
        target=serializers.ChoiceField(choices=['PE','AU','CA']).run_validation(request.data.get('status'))
        obj=mudar_estado(self.get_object(),target,request.user)
        return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['post'])
    def finalizar(self,request,pk=None):
        return Response(self.get_serializer(finalizar(self.get_object())).data)
    @action(detail=True,methods=['get'])
    def comparativo(self,request,pk=None):
        if not request.user.has_perm('compras.view_orcamento'): raise PermissionDenied('Sem permissão para consultar orçamentos.')
        obj=self.get_object()
        qs=Orcamento.objects.filter(solicitacao=obj,empresa_id=self.empresa_id,fornecedor__empresa_id=self.empresa_id).select_related('fornecedor').prefetch_related('orcamentoitens__item')
        return Response({'solicitacao':self.get_serializer(obj).data,'orcamentos':OrcamentoSerializer(qs,many=True).data})


class OrcamentoViewSet(CompraViewSet):
    queryset=Orcamento.objects.select_related('fornecedor','solicitacao').prefetch_related('orcamentoitens__item').order_by('-dt_orcamento','-pk')
    serializer_class=OrcamentoSerializer
    search_fields=('nr_documento','fornecedor__instituicao','solicitacao__descricao')
    def base_queryset(self):
        return self.queryset.filter(empresa_id=self.empresa_id,fornecedor__empresa_id=self.empresa_id,solicitacao__in=solicitacoes_visiveis(self.request.user,self.empresa_id))
    def get_queryset(self):
        qs=super().get_queryset()
        if self.action=='list' and self.request.query_params.get('solicitacao'):
            qs=qs.filter(solicitacao_id=serializers.IntegerField(min_value=1).run_validation(self.request.query_params['solicitacao']))
        return qs
    def get_serializer_context(self):
        return {**super().get_serializer_context(),'solicitacoes':solicitacoes_visiveis(self.request.user,self.empresa_id)}
    def perform_create(self,serializer):
        obj=bloquear_solicitacao(serializer.validated_data['solicitacao'].pk);estado_editavel(obj,{'AB','PE'})
        serializer.save(empresa_id=self.empresa_id)
        if obj.status=='AB': obj.status='PE';obj.save(update_fields=['status'])
    def perform_update(self,serializer):
        obj=bloquear_solicitacao(serializer.instance.solicitacao_id);estado_editavel(obj,{'PE'})
        serializer.instance=Orcamento.objects.select_for_update().get(pk=serializer.instance.pk);serializer.save()
    def perform_destroy(self,instance):
        obj=bloquear_solicitacao(instance.solicitacao_id);estado_editavel(obj,{'PE'})
        instance.orcamentoitens.all().delete();instance.delete()


class OpcoesViewSet(viewsets.GenericViewSet):
    authentication_classes=BaseViewSet.authentication_classes
    permission_classes=(IsAuthenticated,)
    pagination_class=Pagination
    def list(self,request):
        company=empresa_da_requisicao(request);kind=request.query_params.get('tipo')
        access={'unidades':['itens','unidade'],'itens':['solicitacao','orcamento'],'fornecedores':['orcamento'],
                'solicitacoes':['orcamento'],'centros':['solicitacao'],'tipos':['solicitacao'],
                'ufs':['fornecedor'],'municipios':['fornecedor'],'bancos':['fornecedor']}
        if kind not in access: raise ValidationError({'tipo':'Opção inválida.'})
        if not any(request.user.has_perm(f'compras.{verb}_{model}') for model in access[kind] for verb in ('view','add','change')):
            raise PermissionDenied('Sem permissão para consultar estas opções.')
        if kind=='unidades': qs,field=Unidade.objects.filter(empresa_id=company),'descricao'
        elif kind=='itens': qs,field=Itens.objects.filter(empresa_id=company,unidade__empresa_id=company),'descricao'
        elif kind=='fornecedores': qs,field=Fornecedor.objects.filter(empresa_id=company),'instituicao'
        elif kind=='solicitacoes': qs,field=solicitacoes_visiveis(request.user,company),'descricao'
        elif kind=='centros': qs,field=CentroCusto.objects.filter(empresa_id=company),'descricao'
        elif kind=='tipos': qs,field=TipoDespesa.objects.filter(Q(conta__isnull=True)|Q(conta__empresa_id=company)),'descricao'
        elif kind=='ufs': qs,field=Uf.objects.all(),'sigla'
        elif kind=='municipios':
            qs,field=Municipio.objects.all(),'descricao'
            if request.query_params.get('uf'): qs=qs.filter(uf_id=serializers.IntegerField(min_value=1).run_validation(request.query_params['uf']))
        else: qs,field=Banco.objects.all(),'nome'
        if request.query_params.get('search'): qs=qs.filter(**{field+'__icontains':request.query_params['search']})
        if request.query_params.get('id'): qs=qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
        return self.get_paginated_response([{'id':obj.pk,'descricao':str(obj)} for obj in self.paginate_queryset(qs.order_by('pk'))])
