import hashlib
import re
from django.db import transaction,connection
from django.db.models import Q,Value,F
from django.db.models.functions import Replace
from rest_framework import viewsets,serializers
from rest_framework.views import APIView
from rest_framework.permissions import BasePermission,IsAuthenticated
from rest_framework.exceptions import ValidationError,PermissionDenied
from rest_framework.response import Response
from conta.views import BaseViewSet,Pagination
from clientes.models import Municipio,Uf
from .models import Empresa
from .serializers import EmpresaSerializer


class EmpresaPermission(BasePermission):
    def has_permission(self,request,view):
        verb={'create':'add','update':'change','partial_update':'change','destroy':'delete'}.get(view.action,'view')
        return request.user.has_perm(f'empresa.{verb}_empresa')


class EmpresaViewSet(BaseViewSet):
    queryset=Empresa.objects.select_related('cidade','uf').order_by('razao','pk')
    serializer_class=EmpresaSerializer
    permission_classes=(IsAuthenticated,EmpresaPermission)
    search_fields=('razao','cnpj')
    def base_queryset(self):
        return self.queryset.filter(pk__in=self.request.user.empresas.values('pk'))
    def get_serializer_context(self):
        # Cadastro de empresas não exige uma empresa ativa para permitir o primeiro cadastro.
        return {'request':self.request,'view':self,'format':self.format_kwarg}
    def unique_cnpj(self,serializer):
        value=serializer.validated_data.get('cnpj',serializer.instance.cnpj if serializer.instance else '')
        digits=re.sub(r'\D','',value)
        if connection.vendor=='postgresql':
            lock=int.from_bytes(hashlib.sha256(('empresa.cnpj:'+digits).encode()).digest()[:8],'big')&((1<<63)-1)
            with connection.cursor() as cursor:cursor.execute('SELECT pg_advisory_xact_lock(%s)',[lock])
        normalized=F('cnpj')
        for char in ('.','/','-',' '):normalized=Replace(normalized,Value(char),Value(''))
        if Empresa.objects.annotate(_cnpj=normalized).filter(_cnpj=digits).exclude(pk=serializer.instance.pk if serializer.instance else None).exists():
            raise ValidationError({'cnpj':'Este CNPJ já está cadastrado.'})
    def perform_create(self,serializer):
        self.unique_cnpj(serializer)
        obj=serializer.save()
        # Somente o criador recebe vínculo; não altera vínculos de terceiros.
        self.request.user.empresas.add(obj)
    def perform_update(self,serializer):
        self.unique_cnpj(serializer);serializer.save()
    def perform_destroy(self,instance):
        pk=instance.pk;instance.delete()
        if self.request.session.get('empresa')==pk:
            self.request.session.pop('empresa',None);self.request.session.pop('empresa_nome',None)


class SelecionarEmpresaView(APIView):
    authentication_classes=BaseViewSet.authentication_classes
    permission_classes=(IsAuthenticated,)
    def post(self,request):
        pk=serializers.IntegerField(min_value=1).run_validation(request.data.get('empresa',request.data.get('empresa_select')))
        company=request.user.empresas.filter(pk=pk).first()
        if not company:raise PermissionDenied('Empresa fora do seu escopo de acesso.')
        request.session['empresa']=company.pk;request.session['empresa_nome']=company.razao
        return Response({'retorno':'ok','empresa':company.pk,'razao':company.razao})


class OpcoesViewSet(viewsets.GenericViewSet):
    authentication_classes=BaseViewSet.authentication_classes
    permission_classes=(IsAuthenticated,)
    pagination_class=Pagination
    def list(self,request):
        if not any(request.user.has_perm(f'empresa.{verb}_empresa') for verb in ('view','add','change')):
            raise PermissionDenied('Sem permissão para consultar opções de empresas.')
        kind=request.query_params.get('tipo')
        if kind=='ufs':qs,field=Uf.objects.all(),'sigla'
        elif kind=='municipios':
            qs,field=Municipio.objects.all(),'descricao'
            if request.query_params.get('uf'):qs=qs.filter(uf_id=serializers.IntegerField(min_value=1).run_validation(request.query_params['uf']))
        else:raise ValidationError({'tipo':'Escolha ufs ou municipios.'})
        if request.query_params.get('id'):qs=qs.filter(pk=serializers.IntegerField(min_value=1).run_validation(request.query_params['id']))
        if request.query_params.get('search'):qs=qs.filter(**{field+'__icontains':request.query_params['search']})
        return self.get_paginated_response([{'id':obj.pk,'descricao':str(obj)} for obj in self.paginate_queryset(qs.order_by(field,'pk'))])
