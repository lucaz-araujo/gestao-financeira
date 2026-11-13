from django.contrib.auth import get_user_model
from django.utils.crypto import constant_time_compare
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password


class PasswordAwareTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self,attrs):
        token=self.token_class(attrs['refresh'])
        try:self.user=get_user_model().objects.filter(**{api_settings.USER_ID_FIELD:token.get(api_settings.USER_ID_CLAIM)}).first()
        except (ValueError,TypeError):self.user=None
        if self.user is None or not self.user.is_active or not constant_time_compare(str(token.get(api_settings.REVOKE_TOKEN_CLAIM,'')),get_md5_hash_password(self.user.password)):
            raise InvalidToken('Sessão expirada. Entre novamente.')
        return super().validate(attrs)
