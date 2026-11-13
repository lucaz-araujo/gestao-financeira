"""Links assinados e envio por Django EmailBackend, sem credenciais no código."""
import re
from urllib.parse import urlparse
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError as EmailValidationError
from rest_framework.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .services import IntegracaoIndisponivel, NotaConflict

SALT = 'notas.portal.v1'


def public_token(nota, client_list=False):
    payload = {'empresa': nota.empresa_id, 'cliente': nota.contrato.cliente_id}
    if not client_list:
        payload['nota'] = nota.pk
    return signing.dumps(payload, salt=SALT, compress=True)


def public_path(nota, client_list=False):
    return '/notas/publica/' + public_token(nota, client_list) + '/'


def email_status():
    local_test = settings.EMAIL_BACKEND == 'django.core.mail.backends.locmem.EmailBackend'
    url = urlparse(settings.PUBLIC_APP_URL)
    configured = bool(settings.EMAIL_HOST and settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)
    return bool((configured or local_test) and url.scheme == 'https' and url.hostname)


def recipients(nota):
    values = [x.strip() for x in re.split(r'[,;\s]+', nota.contrato.cliente.resp_email or '') if x.strip()]
    if not values:
        raise NotaConflict('O cliente não possui e-mail cadastrado.')
    for value in values:
        try:
            validate_email(value)
        except EmailValidationError:
            raise ValidationError({'cliente': 'Corrija o e-mail cadastrado do cliente.'})
    return list(dict.fromkeys(values))


def check_email(nota):
    if not email_status():
        raise IntegracaoIndisponivel('Configure o servidor de e-mail e a URL pública HTTPS para enviar notas.')
    if not nota.protocolo_recebimento or not nota.numero or nota.cancelada_em:
        raise NotaConflict('Somente notas autorizadas e não canceladas podem ser enviadas ao cliente.')
    recipients(nota)


def send_note_email(nota, client_list=False):
    check_email(nota)
    link = settings.PUBLIC_APP_URL + public_path(nota, client_list)
    html = render_to_string('nota_email.html', {'nota': nota, 'link': link, 'lista': client_list})
    message = EmailMultiAlternatives('Notas fiscais de serviço' if client_list else f'Nota fiscal de serviço {nota.numero}',
                                    strip_tags(html) + '\n\n' + link, settings.DEFAULT_FROM_EMAIL, recipients(nota))
    message.attach_alternative(html, 'text/html')
    if message.send(fail_silently=False) != 1:
        raise RuntimeError('O servidor não confirmou o envio do e-mail.')
    return {'email_enviado': True, 'detail': 'O servidor de e-mail aceitou o envio. A entrega ao destinatário não foi confirmada.'}
