from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError,PermissionDenied
from rest_framework.permissions import BasePermission,IsAuthenticated
from rest_framework.response import Response
from conta.views import BaseViewSet
from notas.gateway import fiscal_status
from .models import Ambiente
from .serializers import AmbienteSerializer
from .services import salvar_ambiente,ajustar_sequencias


class AmbientePermission(BasePermission):
    def has_permission(self,request,view):
        verb={'create':'add','update':'change','partial_update':'change','ajustar_sequencias':'change'}.get(view.action,'view')
        allowed=request.user.has_perm(f'configambiente.{verb}_ambiente')
        return allowed and (view.action!='ajustar_sequencias' or request.user.has_perm('configambiente.ajustar_sequencias_ambiente'))


class AmbienteViewSet(BaseViewSet):
    queryset=Ambiente.objects.select_related('empresa').order_by('pk')
    serializer_class=AmbienteSerializer
    permission_classes=(IsAuthenticated,AmbientePermission)
    search_fields=('descricao',)
    http_method_names=['get','post','put','patch','head','options']
    def perform_create(self,serializer):
        from empresa.models import Empresa
        Empresa.objects.select_for_update().get(pk=self.empresa_id)
        if Ambiente.objects.filter(empresa_id=self.empresa_id).exists():
            raise ValidationError({'empresa':'Esta empresa já possui ambiente fiscal. Edite o registro existente.'})
        salvar_ambiente(serializer,self.request.user,self.empresa_id)
    def perform_update(self,serializer):salvar_ambiente(serializer,self.request.user,self.empresa_id)
    @action(detail=True,methods=['get'])
    def prontidao(self,request,pk=None):return Response(fiscal_status(self.get_object().empresa_id))
    @action(detail=True,methods=['post'])
    @transaction.atomic
    def ajustar_sequencias(self,request,pk=None):
        confirmed=serializers.BooleanField().run_validation(request.data.get('confirmar'))
        if not confirmed:raise ValidationError({'confirmar':'Confirme o ajuste dos contadores fiscais.'})
        lote=serializers.IntegerField(min_value=0,max_value=2147483646).run_validation(request.data.get('numero_lote'))
        rps=serializers.IntegerField(min_value=0,max_value=2147483646).run_validation(request.data.get('numero_rps'))
        from django.shortcuts import get_object_or_404
        obj=get_object_or_404(self.get_queryset().select_for_update(of=('self',)),pk=pk)
        return Response(self.get_serializer(ajustar_sequencias(obj,request.user,lote,rps)).data)
    def handle_exception(self,exc):
        if isinstance(exc,ModelValidationError):exc=ValidationError(exc.message_dict if hasattr(exc,'message_dict') else exc.messages)
        return super().handle_exception(exc)
    def finalize_response(self,request,response,*args,**kwargs):
        response=super().finalize_response(request,response,*args,**kwargs);response['Cache-Control']='no-store';return response
