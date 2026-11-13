from django.conf import settings
from django.db import DatabaseError
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework.exceptions import APIException
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from . import serializers, services


class LegacyIPThrottle(SimpleRateThrottle):
    rate = settings.API_LEGACY_RATE
    scope = 'integracao-legada-ip'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': request.META.get('REMOTE_ADDR', '')}


@method_decorator(sensitive_post_parameters('key', 'dados'), name='dispatch')
class IntegracaoView(APIView):
    # Estes consumidores usam assinatura própria, sem cookies nem JWT.
    authentication_classes = ()
    permission_classes = (AllowAny,)
    parser_classes = (FormParser, MultiPartParser, JSONParser)
    renderer_classes = (JSONRenderer,)
    throttle_classes = (LegacyIPThrottle,)
    serializer_class = serializers.CompetenciaSerializer
    kind = 'delphi'
    operation = staticmethod(services.liberar)

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response({'error': 'Parametros de requisição incorretos'})
        data = serializer.validated_data
        if self.kind and not services.autenticar(data, self.kind):
            return Response({'error': 'Parametros de requisição incorretos'})
        return Response(self.operation(data))

    def handle_exception(self, exc):
        if isinstance(exc, DatabaseError):
            exc = services.IntegracaoIndisponivel()
        response = super().handle_exception(exc)
        # O envelope error é parte do contrato externo. A falha não libera acesso.
        response.data = {'error': 'Somente por POST' if response.status_code == 405 else str(exc.detail) if isinstance(exc, APIException) and isinstance(exc.detail, str) else 'Não foi possível processar a requisição.'}
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class WebView(IntegracaoView):
    serializer_class = serializers.WebSerializer
    kind = 'web'
    operation = staticmethod(services.liberar_web)


class TransparenciaView(IntegracaoView):
    serializer_class = serializers.TransparenciaSerializer
    kind = 'transparencia'
    operation = staticmethod(lambda data: services.liberar(data, transparencia=True))


class ServicoView(IntegracaoView):
    serializer_class = serializers.ServicoSerializer
    kind = 'servico'
    operation = staticmethod(services.liberar_servico)


class BloqueioView(IntegracaoView):
    serializer_class = serializers.BloqueioSerializer
    operation = staticmethod(services.consultar_bloqueio)


class EntidadeView(IntegracaoView):
    serializer_class = serializers.MunicipioSerializer
    kind = None
    operation = staticmethod(services.entidades_publicas)

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        return Response(self.operation(serializer.validated_data) if serializer.is_valid() else [])


class RecadView(IntegracaoView):
    serializer_class = serializers.RecadSerializer
    operation = staticmethod(lambda data: {})


# Mantém os callables e nomes de reverse usados pelas integrações existentes.
liberames = WebView.as_view()
liberames_delphi = IntegracaoView.as_view()
libera_transparencia = TransparenciaView.as_view()
liberames_servico = ServicoView.as_view()
bloqueia = BloqueioView.as_view()
cod_entidade = EntidadeView.as_view()
recad_delphi = RecadView.as_view()
