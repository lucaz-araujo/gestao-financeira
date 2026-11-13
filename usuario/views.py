import hashlib
from urllib.parse import quote,urlencode
from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from django.db import transaction,connection,IntegrityError
from rest_framework import mixins,viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import APIException,ValidationError
from rest_framework.permissions import IsAuthenticated,AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle,UserRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication
from clientes.auth_api import CookieAPIView,LoginView,LogoutView,csrf,COOKIE,COOKIE_PATH
from conta.services import ContaConflict
from .models import Usuario
from .serializers import UsuarioSerializer,TrocaSenhaSerializer,RecuperacaoSolicitarSerializer,RecuperacaoConfirmarSerializer
from .services import trocar_senha,confirmar_recuperacao,solicitar_recuperacao,recovery_available,GENERIC_RECOVERY,auditar


def limpar_sessao(request,response):
    django_logout(request._request)
    response.delete_cookie(COOKIE,path=COOKIE_PATH,samesite='Lax')
    response['Cache-Control']='no-store'
    return response


class ProfileThrottle(UserRateThrottle):
    rate='20/min';scope='usuario-profile'
class PasswordThrottle(UserRateThrottle):
    rate='5/min';scope='usuario-password'
class RecoveryIPThrottle(SimpleRateThrottle):
    rate='20/hour';scope='usuario-recovery-ip'
    def get_cache_key(self,request,view):return self.cache_format%{'scope':self.scope,'ident':request.META.get('REMOTE_ADDR','')}
class RecoveryIdentityThrottle(SimpleRateThrottle):
    rate='5/hour';scope='usuario-recovery-identity'
    def get_cache_key(self,request,view):
        text=str(request.data.get('username','')).strip().casefold()+'|'+str(request.data.get('email','')).strip().casefold()
        return self.cache_format%{'scope':self.scope,'ident':hashlib.sha256(text.encode()).hexdigest()}


@method_decorator(sensitive_post_parameters('password','email_password','current_password','new_password','conf_password'),name='dispatch')
class PerfilViewSet(mixins.RetrieveModelMixin,mixins.UpdateModelMixin,viewsets.GenericViewSet):
    queryset=Usuario.objects.all()
    serializer_class=UsuarioSerializer
    authentication_classes=(JWTAuthentication,SessionAuthentication)
    permission_classes=(IsAuthenticated,)
    throttle_classes=(ProfileThrottle,)
    def get_object(self):
        # Qualquer ID legado precisa ser o próprio usuário; privilégios não ampliam esta API pessoal.
        from rest_framework.exceptions import NotFound
        pk=self.kwargs.get('pk')
        if pk is not None and str(pk)!=str(self.request.user.pk):raise NotFound()
        qs=self.get_queryset()
        if self.action in ('update','partial_update'):qs=qs.select_for_update()
        return qs.get(pk=self.request.user.pk)
    @transaction.atomic
    def update(self,*args,**kwargs):return super().update(*args,**kwargs)
    def perform_update(self,serializer):
        value=serializer.validated_data.get('email')
        if value and connection.vendor=='postgresql':
            lock=int.from_bytes(hashlib.sha256(('usuario.email:'+value.casefold()).encode()).digest()[:8],'big')&((1<<63)-1)
            with connection.cursor() as cursor:cursor.execute('SELECT pg_advisory_xact_lock(%s)',[lock])
            if Usuario.objects.filter(email__iexact=value).exclude(pk=self.request.user.pk).exists():raise ValidationError({'email':'Este e-mail já está cadastrado.'})
        file=serializer.validated_data.get('avatar');obj=serializer.instance
        old_avatar=obj.avatar.name
        try:
            obj=serializer.save();auditar(obj,[field for field in serializer.validated_data if field not in ('remover_avatar','email_password')])
        except Exception:
            if file and obj.avatar and obj.avatar._committed and obj.avatar.name!=old_avatar:obj.avatar.storage.delete(obj.avatar.name)
            raise
    @action(detail=False,methods=['post'],throttle_classes=(PasswordThrottle,))
    def senha(self,request):
        data=TrocaSenhaSerializer(data=request.data);data.is_valid(raise_exception=True)
        trocar_senha(request.user,data.validated_data['current_password'],data.validated_data['new_password'])
        return limpar_sessao(request,Response({'detail':'Senha alterada. Entre novamente.'}))
    def handle_exception(self,exc):
        if isinstance(exc,IntegrityError):exc=ContaConflict('Os dados conflitam com outro cadastro. Nenhuma alteração foi gravada.')
        return super().handle_exception(exc)
    def finalize_response(self,request,response,*args,**kwargs):
        response=super().finalize_response(request,response,*args,**kwargs);response['Cache-Control']='no-store';return response


class RecoveryUnavailable(APIException):
    status_code=503
    default_detail='A recuperação por e-mail está indisponível. Contate o administrador.'


class RecoveryRequestView(CookieAPIView):
    authentication_classes=()
    permission_classes=(AllowAny,)
    throttle_classes=(RecoveryIPThrottle,RecoveryIdentityThrottle)
    def post(self,request):
        csrf(request)
        serializer=RecuperacaoSolicitarSerializer(data=request.data);serializer.is_valid(raise_exception=True)
        if not recovery_available():raise RecoveryUnavailable()
        try:solicitar_recuperacao(**serializer.validated_data)
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Falha ao entregar instruções de recuperação; operação revertida.')
        return Response({'detail':GENERIC_RECOVERY})


@method_decorator(sensitive_post_parameters('token','new_password','conf_password'),name='dispatch')
class RecoveryConfirmView(CookieAPIView):
    authentication_classes=()
    permission_classes=(AllowAny,)
    throttle_classes=(RecoveryIPThrottle,)
    def post(self,request):
        csrf(request)
        serializer=RecuperacaoConfirmarSerializer(data=request.data);serializer.is_valid(raise_exception=True)
        confirmar_recuperacao(serializer.validated_data['token'],serializer.validated_data['new_password'])
        return limpar_sessao(request,Response({'detail':'Senha alterada. Entre novamente.'}))


@require_http_methods(['GET','POST'])
def login_view(request):
    if request.method=='POST':return LoginView.as_view()(request)
    target=request.GET.get('next','')
    safe=target.startswith('/') and not target.startswith('//') and url_has_allowed_host_and_scheme(target,{request.get_host()},require_https=request.is_secure())
    return redirect('/clientes/app/'+('?' + urlencode({'next':target}) if safe else ''))


@require_http_methods(['GET','POST'])
def logout_view(request):
    if request.method=='POST':return LogoutView.as_view()(request)
    return redirect('/clientes/app/sair')


def recuperar_legado(request,token=None):
    return redirect('/clientes/app/recuperar-senha'+('#token='+quote(token,safe='') if token and len(token)<=128 else ''))
