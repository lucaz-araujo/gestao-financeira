"""Identidade de rede somente a partir do proxy explicitamente confiável."""
from ipaddress import ip_address
from django.conf import settings
from django.core.exceptions import SuspiciousOperation


class TrustedProxyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, 'TRUST_PROXY_HTTPS', False):
            peer = request.META.get('REMOTE_ADDR', '')
            if peer in settings.TRUSTED_PROXY_IPS:
                value = request.META.get('HTTP_X_REAL_IP')
                if value:
                    try:
                        request.META['REMOTE_ADDR'] = str(ip_address(value))
                    except ValueError:
                        raise SuspiciousOperation('Endereço de origem inválido.')
            else:
                # Impede que um cliente direto se declare proxy HTTPS.
                for name in ('HTTP_X_FORWARDED_PROTO', 'HTTP_X_REAL_IP', 'HTTP_X_FORWARDED_FOR'):
                    request.META.pop(name, None)
        return self.get_response(request)
