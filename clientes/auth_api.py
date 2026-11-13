"""Sessão do frontend: access em memória e refresh em cookie HttpOnly."""
from django.conf import settings
from django.contrib.auth import login as django_login, logout as django_logout
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from usuario.tokens import PasswordAwareTokenRefreshSerializer
from django.middleware.csrf import get_token
from rest_framework import serializers
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied, AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

COOKIE = 'clientes_refresh'
COOKIE_PATH = '/clientes/api/auth/'


def csrf(request):
    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied('Falha na proteção CSRF. Atualize a página e tente novamente.')


def establish_session(request,user):
    raw=request._request
    if str(raw.session.get('_auth_user_id'))!=str(user.pk) or raw.session.get('_auth_user_hash')!=user.get_session_auth_hash():
        django_login(raw,user,backend=getattr(user,'backend',settings.AUTHENTICATION_BACKENDS[0]))
    request.user=user
    raw.session.set_expiry(int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()))
    selected=user.empresas.filter(pk=raw.session.get('empresa')).first()
    selected=selected or user.empresas.order_by('razao','pk').first()
    if selected:
        raw.session['empresa']=selected.pk;raw.session['empresa_nome']=selected.razao
    else:
        raw.session.pop('empresa',None);raw.session.pop('empresa_nome',None)


def token_response(data,request=None):
    response = Response({'access': data['access'], **({'csrfToken':get_token(request)} if request else {})})
    response.set_cookie(COOKIE, data['refresh'], httponly=True, secure=settings.CLIENTES_AUTH_COOKIE_SECURE,
                        samesite='Lax', path=COOKIE_PATH,
                        max_age=int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()))
    response['Cache-Control'] = 'no-store'
    return response


class LoginThrottle(AnonRateThrottle):
    rate = '10/min'
    scope = 'login-ip'


class CookieAPIView(APIView):
    def get_authenticate_header(self, request):
        return 'Bearer realm="api"'

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class CsrfView(CookieAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        response = Response({'csrfToken': get_token(request)})
        response['Cache-Control'] = 'no-store'
        return response


@method_decorator(sensitive_post_parameters('password'),name='dispatch')
class LoginView(CookieAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (LoginThrottle,)

    def post(self, request):
        csrf(request)
        serializer = TokenObtainPairSerializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed:
            raise AuthenticationFailed("Usuário ou senha inválidos.")
        except TokenError as exc:
            raise InvalidToken(str(exc))
        establish_session(request,serializer.user)
        return token_response(serializer.validated_data,request)


class RefreshView(CookieAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        csrf(request)
        value = request.COOKIES.get(COOKIE)
        if not value:
            raise InvalidToken('Sessão expirada. Entre novamente.')
        serializer = PasswordAwareTokenRefreshSerializer(data={'refresh': value})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken('Sessão expirada. Entre novamente.') from exc
        establish_session(request,serializer.user)
        return token_response(serializer.validated_data,request)


class LogoutView(CookieAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        csrf(request)
        value = request.COOKIES.get(COOKIE)
        if value:
            try:
                RefreshToken(value).blacklist()
            except TokenError:
                pass
        django_logout(request._request)
        response = Response(status=204)
        response.delete_cookie(COOKIE, path=COOKIE_PATH, samesite='Lax')
        response['Cache-Control'] = 'no-store'
        return response


class EmpresaResumoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    razao = serializers.CharField()
    cnpj = serializers.CharField()


class MeView(APIView):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        user = request.user
        response = Response({'id': user.pk, 'username': user.username,
                             'nome': user.get_full_name() or user.username, 'uf': user.uf_id,
                             'avatar': request.build_absolute_uri(user.avatar.url) if user.avatar else None,
                             'permissions': sorted(user.get_all_permissions()),
                             'empresas': EmpresaResumoSerializer(user.empresas.order_by('razao'), many=True).data})
        response['Cache-Control'] = 'no-store'
        return response


# Os aliases JWT também precisam limitar tentativas; não passam pelo login React.
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


class RefreshThrottle(AnonRateThrottle):
    rate = '60/min'
    scope = 'refresh-ip'


@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class LimitedTokenObtainPairView(TokenObtainPairView):
    throttle_classes = (LoginThrottle,)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


@method_decorator(sensitive_post_parameters('refresh'), name='dispatch')
class LimitedTokenRefreshView(TokenRefreshView):
    throttle_classes = (RefreshThrottle,)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response
