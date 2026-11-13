import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlsplit,urlunsplit
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ModelValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError,AuthenticationFailed
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken,BlacklistedToken
from .models import Usuario,EsqueceuSenha

logger=logging.getLogger(__name__)
GENERIC_RECOVERY='Se os dados corresponderem a uma conta ativa, você receberá as instruções por e-mail.'
INVALID_RESET='Link inválido ou expirado. Solicite uma nova recuperação.'


def auditar(user,fields):
    from auditlog.models import LogEntry
    LogEntry.objects.log_create(user,action=LogEntry.Action.UPDATE,actor=user,serialized_data=None,changes={field:[None,'alterado'] for field in fields})


def revogar_acessos(user):
    EsqueceuSenha.objects.filter(usuario=user,ativo=True).update(ativo=False)
    ids=OutstandingToken.objects.filter(user=user).values_list('pk',flat=True)
    BlacklistedToken.objects.bulk_create([BlacklistedToken(token_id=pk) for pk in ids],ignore_conflicts=True,batch_size=500)


def nova_senha(user,password):
    try:validate_password(password,user)
    except ModelValidationError as exc:raise ValidationError({'new_password':exc.messages})
    user.set_password(password);user.save(update_fields=['password'])
    revogar_acessos(user);auditar(user,['senha'])


@transaction.atomic
def trocar_senha(user,current_password,new_password):
    user=Usuario.objects.select_for_update().filter(pk=user.pk,is_active=True).first()
    if not user:raise AuthenticationFailed('Sessão expirada. Entre novamente.')
    if not user.check_password(current_password):raise ValidationError({'current_password':'Senha atual incorreta.'})
    nova_senha(user,new_password)


def recovery_origin():
    parsed=urlsplit(settings.PUBLIC_APP_URL)
    if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment or (not settings.DEBUG and parsed.scheme!='https'):
        return None
    return parsed


def recovery_available():
    if recovery_origin() is None:return False
    if settings.EMAIL_BACKEND in ('django.core.mail.backends.console.EmailBackend','django.core.mail.backends.dummy.EmailBackend','django.core.mail.backends.filebased.EmailBackend'):return False
    smtp=settings.EMAIL_BACKEND=='django.core.mail.backends.smtp.EmailBackend'
    return not smtp or bool(settings.EMAIL_HOST and (not settings.EMAIL_HOST_USER or settings.EMAIL_HOST_PASSWORD))


@transaction.atomic
def solicitar_recuperacao(username,email):
    user=Usuario.objects.select_for_update().filter(username=username,email__iexact=email,is_active=True).first()
    if user is None or not user.has_usable_password():return
    raw=str(user.pk)+'.'+secrets.token_urlsafe(32)
    EsqueceuSenha.objects.filter(usuario=user,ativo=True).update(ativo=False)
    record=EsqueceuSenha.objects.create(usuario=user,token=hashlib.sha256((raw+'\0'+user.password).encode()).hexdigest(),data=timezone.now(),ativo=True)
    origin=recovery_origin()
    link=urlunsplit((origin.scheme,origin.netloc,'/clientes/app/recuperar-senha','','token='+raw))
    # Não usa Host da requisição nem expõe a existência da conta na resposta pública.
    sent=send_mail('Recuperação de acesso — Layout Sistemas',
        'Foi solicitada uma nova senha para sua conta.\n\n'+link+f'\n\nEste link expira em {settings.USUARIO_PASSWORD_RESET_TIMEOUT//60} minutos e pode ser usado uma única vez. Se não solicitou a recuperação, ignore esta mensagem.',
        settings.DEFAULT_FROM_EMAIL,[user.email],fail_silently=False)
    if sent!=1:raise RuntimeError('Falha na entrega da recuperação.')


@transaction.atomic
def confirmar_recuperacao(token,new_password):
    try:
        identity,secret=token.split('.',1)
        if not identity.isascii() or not identity.isdigit() or not 0<int(identity)<=9223372036854775807 or len(secret)!=43:raise ValueError
    except (ValueError,TypeError):raise ValidationError({'token':INVALID_RESET})
    user=Usuario.objects.select_for_update().filter(pk=int(identity),is_active=True).first()
    if not user or not user.has_usable_password():raise ValidationError({'token':INVALID_RESET})
    digest=hashlib.sha256((token+'\0'+user.password).encode()).hexdigest()
    record=EsqueceuSenha.objects.select_for_update().filter(usuario=user,token=digest,ativo=True).first()
    if not record or record.data<timezone.now()-timedelta(seconds=settings.USUARIO_PASSWORD_RESET_TIMEOUT):
        raise ValidationError({'token':INVALID_RESET})
    nova_senha(user,new_password)
    return user
