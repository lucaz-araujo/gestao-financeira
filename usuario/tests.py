import hashlib
import tempfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
from PIL import Image
from django.conf import settings
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings,Client
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken,RefreshToken
from empresa.models import Empresa
from .models import Usuario,EsqueceuSenha

OLD='Initial-test-passphrase-918!'
NEW='Another-test-passphrase-729!'

@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',PUBLIC_APP_URL='https://example.test')
class UsuarioAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=Usuario.objects.create_user(username='perfil_test',email='perfil@example.test',password=OLD,first_name='Pessoa')
        cls.other=Usuario.objects.create_user(username='other_test',email='other@example.test',password=OLD)
        cls.company=Empresa.objects.create(cnpj='1',razao='Empresa teste');cls.other.empresas.add(cls.company)
    def setUp(self):
        cache.clear();self.client=APIClient(enforce_csrf_checks=True)
        self.access=str(AccessToken.for_user(self.user));self.client.credentials(HTTP_AUTHORIZATION='Bearer '+self.access)
        self.media=self.enterContext(tempfile.TemporaryDirectory());self.enterContext(self.settings(MEDIA_ROOT=self.media))
    def public(self):
        client=APIClient(enforce_csrf_checks=True);token=client.get('/clientes/api/auth/csrf/').data['csrfToken'];return client,token
    def request_reset(self,client=None,csrf=None,**values):
        if client is None:client,csrf=self.public()
        response=client.post('/usuario/api/recuperacao/solicitar/',{'username':self.user.username,'email':self.user.email,**values},format='json',HTTP_X_CSRFTOKEN=csrf)
        return response
    def recovery_token(self):
        response=self.request_reset();self.assertEqual(response.status_code,200,response.data)
        link=next(line for line in mail.outbox[-1].body.splitlines() if line.startswith('https://'))
        return parse_qs(urlsplit(link).fragment)['token'][0]
    def confirm(self,token,**values):
        client,csrf=self.public();return client.post('/usuario/api/recuperacao/confirmar/',{'token':token,'new_password':NEW,'conf_password':NEW,**values},format='json',HTTP_X_CSRFTOKEN=csrf)
    def test_profile_is_own_only_even_without_company_or_model_permission(self):
        response=self.client.get('/usuario/api/perfil/');self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['username'],self.user.username)
        for field in ['password','is_staff','is_superuser','groups','user_permissions','empresas','uf']:self.assertNotIn(field,response.data)
        self.assertEqual(self.client.get(f'/usuario/edit/{self.other.pk}/').status_code,404)
        self.assertEqual(self.client.patch(f'/usuario/edit/{self.other.pk}/',{'first_name':'Changed'},format='json').status_code,404)
        self.assertEqual(APIClient().get('/usuario/api/perfil/').status_code,401)
    def test_profile_mass_assignment_cannot_change_privileges_password_or_tenant(self):
        response=self.client.patch('/usuario/api/perfil/',{'first_name':'Atualizado','is_superuser':True,'is_staff':True,'is_active':False,'groups':[1],'user_permissions':[1],'empresas':[self.company.pk],'password':'plain','username':'hacked','uf':999},format='json')
        self.assertEqual(response.status_code,200,response.data);self.user.refresh_from_db()
        self.assertFalse(self.user.is_superuser);self.assertFalse(self.user.is_staff);self.assertTrue(self.user.is_active);self.assertFalse(self.user.empresas.exists());self.assertEqual(self.user.username,'perfil_test');self.assertTrue(self.user.check_password(OLD))
    def test_profile_validation_email_cpf_phone_and_pagination(self):
        for data in [{'email':'bad'},{'email':self.other.email.upper()},{'cpf':'00000000000'},{'cpf':'123'},{'fone':'bad'},{'linhas':0},{'linhas':201}]:
            response=self.client.patch('/usuario/api/perfil/',data,format='json');self.assertEqual(response.status_code,400,response.data)
        response=self.client.patch('/usuario/api/perfil/',{'cpf':'529.982.247-25','fone':'85999990000','linhas':25},format='json');self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['cpf'],'52998224725')
    def test_avatar_validated_safe_name_preserved_and_removed(self):
        output=BytesIO();Image.new('RGB',(8,8),'red').save(output,format='PNG')
        response=self.client.patch('/usuario/api/perfil/',{'avatar':SimpleUploadedFile('untrusted.png',output.getvalue(),content_type='image/png')},format='multipart');self.assertEqual(response.status_code,200,response.data)
        self.user.refresh_from_db();path=Path(self.user.avatar.path);self.assertTrue(path.exists());self.assertNotIn('untrusted',path.name)
        self.assertEqual(self.client.patch('/usuario/api/perfil/',{'first_name':'Editado'},format='json').status_code,200)
        self.user.refresh_from_db();self.assertEqual(Path(self.user.avatar.path),path)
        response=self.client.patch('/usuario/api/perfil/',{'remover_avatar':True,'avatar':SimpleUploadedFile('conflict.png',output.getvalue(),content_type='image/png')},format='multipart')
        self.assertEqual(response.status_code,400,response.data)
        self.user.refresh_from_db();self.assertEqual(Path(self.user.avatar.path),path);self.assertTrue(path.exists())
        self.assertEqual(self.client.patch('/usuario/api/perfil/',{'remover_avatar':True},format='json').status_code,200);self.assertTrue(path.exists())
        self.assertEqual(self.client.patch('/usuario/api/perfil/',{'avatar':SimpleUploadedFile('bad.png',b'bad')},format='multipart').status_code,400)
    def test_password_change_requires_current_strong_and_matching_password(self):
        for data in [{'current_password':'wrong','new_password':NEW,'conf_password':NEW},{'current_password':OLD,'new_password':'short','conf_password':'short'},{'current_password':OLD,'new_password':NEW,'conf_password':'different'}]:
            response=self.client.post('/usuario/api/perfil/senha/',data,format='json');self.assertEqual(response.status_code,400,response.data)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password(OLD))
    def test_password_change_revokes_access_refresh_legacy_session_and_recovery(self):
        refresh=str(RefreshToken.for_user(self.user));record=EsqueceuSenha.objects.create(usuario=self.user,token='old-token',data=timezone.now(),ativo=True)
        legacy=Client();legacy.force_login(self.user)
        response=self.client.post('/usuario/api/perfil/senha/',{'current_password':OLD,'new_password':NEW,'conf_password':NEW},format='json');self.assertEqual(response.status_code,200,response.data)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password(NEW));self.assertFalse(self.user.check_password(OLD))
        self.assertEqual(self.client.get('/clientes/api/auth/me/').status_code,401)
        anonymous=APIClient();self.assertEqual(anonymous.post('/api/token/refresh/',{'refresh':refresh},format='json').status_code,401)
        record.refresh_from_db();self.assertFalse(record.ativo)
        self.assertEqual(legacy.get('/usuario/api/perfil/').status_code,401)
    def test_login_creates_session_and_rotates_csrf_then_refresh_and_logout_work(self):
        client,csrf=self.public();response=client.post('/clientes/api/auth/login/',{'username':self.user.username,'password':OLD},format='json',HTTP_X_CSRFTOKEN=csrf);self.assertEqual(response.status_code,200,response.data)
        new_csrf=response.data['csrfToken'];self.assertEqual(int(client.session['_auth_user_id']),self.user.pk)
        self.assertEqual(client.get('/usuario/api/perfil/').status_code,200)
        self.assertEqual(client.post('/clientes/api/auth/refresh/',HTTP_X_CSRFTOKEN=csrf).status_code,403)
        response=client.post('/clientes/api/auth/refresh/',HTTP_X_CSRFTOKEN=new_csrf);self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(client.post('/clientes/api/auth/logout/',HTTP_X_CSRFTOKEN=response.data['csrfToken']).status_code,204)
        self.assertNotIn('_auth_user_id',client.session)
    def test_token_without_password_marker_cannot_authenticate_or_refresh(self):
        token=RefreshToken.for_user(self.user);del token['hash_password']
        self.assertEqual(APIClient().post('/api/token/refresh/',{'refresh':str(token)},format='json').status_code,401)
        client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+str(token.access_token));self.assertEqual(client.get('/usuario/api/perfil/').status_code,401)
    def test_recovery_random_hash_no_account_enumeration_and_single_use(self):
        token=self.recovery_token();record=EsqueceuSenha.objects.get(usuario=self.user,ativo=True)
        self.assertEqual(len(record.token),64);self.assertNotEqual(record.token,hashlib.sha256(token.encode()).hexdigest());self.assertNotEqual(record.token,token)
        response=self.request_reset(username='unknown',email='unknown@example.test');self.assertEqual(response.status_code,200)
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(self.confirm(token).status_code,200);self.assertEqual(self.confirm(token).status_code,400)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password(NEW))
    def test_recovery_expiry_checked_on_post_and_new_request_revokes_previous(self):
        first=self.recovery_token();second=self.recovery_token();self.assertNotEqual(first,second)
        self.assertEqual(self.confirm(first).status_code,400)
        EsqueceuSenha.objects.filter(usuario=self.user,ativo=True).update(data=timezone.now()-timedelta(minutes=31))
        self.assertEqual(self.confirm(second).status_code,400);self.user.refresh_from_db();self.assertTrue(self.user.check_password(OLD))
    def test_recovery_confirmation_applies_password_validation_without_consuming_token(self):
        token=self.recovery_token();self.assertEqual(self.confirm(token,new_password='short',conf_password='short').status_code,400)
        self.assertEqual(self.confirm(token).status_code,200)
    def test_recovery_is_csrf_protected_throttled_and_cannot_use_request_host(self):
        client,csrf=self.public();self.assertEqual(client.post('/usuario/api/recuperacao/solicitar/',{'username':self.user.username,'email':self.user.email},format='json').status_code,403)
        for _ in range(5):self.request_reset(client,csrf,username='unknown',email='unknown@example.test')
        self.assertEqual(self.request_reset(client,csrf,username='unknown',email='unknown@example.test').status_code,429)
        cache.clear();token=self.recovery_token();self.assertIn('https://example.test/clientes/app/recuperar-senha#token=',mail.outbox[-1].body)
    def test_recovery_unconfigured_is_uniformly_unavailable_without_records(self):
        with self.settings(PUBLIC_APP_URL=''):
            self.assertEqual(self.request_reset().status_code,503)
            self.assertEqual(self.request_reset(username='unknown',email='unknown@example.test').status_code,503)
        self.assertFalse(EsqueceuSenha.objects.exists())
    def test_email_failure_rolls_back_request_without_public_account_signal(self):
        with patch('usuario.services.send_mail',side_effect=RuntimeError('synthetic transport failure')):
            response=self.request_reset()
        self.assertEqual(response.status_code,200);self.assertFalse(EsqueceuSenha.objects.exists())
    def test_legacy_routes_redirect_safely_and_logout_get_does_not_mutate(self):
        client=Client();client.force_login(self.user)
        self.assertEqual(client.get('/usuario/logout/').url,'/clientes/app/sair');self.assertIn('_auth_user_id',client.session)
        self.assertEqual(client.get('/usuario/login/',{'next':'https://evil.example/'}).url,'/clientes/app/')
        self.assertIn('next=',client.get('/usuario/login/',{'next':'/dashboard/dashboard/'}).url)
        self.assertEqual(client.get('/usuario/esqueceusenha/').url,'/clientes/app/recuperar-senha')
    def test_non_superuser_admin_cannot_manage_other_users_or_escalate(self):
        self.user.is_staff=True;self.user.save();self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='usuario'))
        client=Client();client.force_login(self.user)
        response=client.post(f'/admin/usuario/usuario/{self.other.pk}/change/',{'is_superuser':True})
        self.assertEqual(response.status_code,302);self.assertEqual(response.url,'/admin/')
        self.other.refresh_from_db();self.assertFalse(self.other.is_superuser)
    def test_admin_creates_user_with_password_hash(self):
        root=Usuario.objects.create_superuser(username='root_user',email='root@example.test',password=OLD)
        client=Client();client.force_login(root)
        response=client.post('/admin/usuario/usuario/add/',{'username':'new_admin_user','first_name':'Novo','last_name':'Usuário','email':'new@example.test','usable_password':'true','password1':NEW,'password2':NEW,'_save':'Salvar'})
        self.assertEqual(response.status_code,302)
        user=Usuario.objects.get(username='new_admin_user');self.assertTrue(user.check_password(NEW));self.assertNotEqual(user.password,NEW)

    def test_email_change_requires_current_password(self):
        response=self.client.patch('/usuario/api/perfil/',{'email':'new-address@example.test'},format='json')
        self.assertEqual(response.status_code,400,response.data)
        response=self.client.patch('/usuario/api/perfil/',{'email':'new-address@example.test','email_password':OLD},format='json')
        self.assertEqual(response.status_code,200,response.data);self.assertNotIn('email_password',response.data)
        self.user.refresh_from_db();self.assertEqual(self.user.email,'new-address@example.test')
    def test_password_recovery_cannot_enable_disabled_local_password(self):
        token=self.recovery_token();self.user.set_unusable_password();self.user.save(update_fields=['password'])
        self.assertEqual(self.confirm(token).status_code,400)
        before=len(mail.outbox);self.assertEqual(self.request_reset().status_code,200);self.assertEqual(len(mail.outbox),before)

    def test_admin_or_cli_password_change_also_invalidates_issued_recovery_link(self):
        token=self.recovery_token();self.user.set_password(NEW);self.user.save(update_fields=['password'])
        self.assertEqual(self.confirm(token).status_code,400)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password(NEW))
