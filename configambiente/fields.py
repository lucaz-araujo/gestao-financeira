"""Campo de senha criptografado; lê valores legados durante a migração."""
import base64
import hashlib
from cryptography.fernet import Fernet,InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

PREFIX='fernet:v1:'

def cipher(secret):
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('certificado-senha-v1:'+secret).encode()).digest()))


class CertificatePasswordField(models.TextField):
    def from_db_value(self,value,expression,connection):
        if not value or not value.startswith(PREFIX):return value
        for secret in [settings.SECRET_KEY,*getattr(settings,'SECRET_KEY_FALLBACKS',[])]:
            try:return cipher(secret).decrypt(value[len(PREFIX):].encode()).decode()
            except InvalidToken:continue
        raise ValidationError('Não foi possível abrir a credencial fiscal. Revise a chave de criptografia da aplicação.')
    def get_prep_value(self,value):
        value=super().get_prep_value(value)
        if not value:return ''
        # Valores da aplicação são sempre texto puro; não aceita ciphertext como atalho.
        return PREFIX+cipher(settings.SECRET_KEY).encrypt(str(value).encode()).decode()
