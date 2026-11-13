import os
import secrets
import subprocess
import tempfile
import types
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail
from django.core.cache import cache
from django.http import JsonResponse
from django.test import override_settings
from django.urls import get_resolver,path
from . import tests as fixtures
@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',PUBLIC_APP_URL='https://example.test')
class UsuarioBrowserTests(StaticLiveServerTestCase):
    def test_account_frontend(self):
        cache.clear();fixtures.UsuarioAPITests.setUpTestData.__func__(type(self))
        media=self.enterContext(tempfile.TemporaryDirectory());self.enterContext(self.settings(MEDIA_ROOT=media))
        nonce=secrets.token_urlsafe(20)
        def local_outbox(request):
            body=mail.outbox[-1].body if getattr(mail,'outbox',[]) else ''
            return JsonResponse({'link':next((line for line in body.splitlines() if line.startswith('https://')),'')})
        urls=types.ModuleType('usuario_isolated_e2e_urls');urls.urlpatterns=[path('_test_mail/'+nonce+'/',local_outbox),*get_resolver().url_patterns]
        self.enterContext(self.settings(ROOT_URLCONF=urls))
        env={**os.environ,'E2E_BASE_URL':self.live_server_url,'E2E_USERNAME':self.user.username,'E2E_EMAIL':self.user.email,'E2E_PASSWORD':fixtures.OLD,'E2E_NEW_PASSWORD':fixtures.NEW,'E2E_RESET_PASSWORD':'Recovered-test-passphrase-346!','E2E_MAIL_PATH':'/_test_mail/'+nonce+'/','PLAYWRIGHT_BROWSERS_PATH':'/tmp/gestao-playwright'}
        result=subprocess.run(['node_modules/.bin/playwright','test','usuario.spec.ts'],cwd=settings.BASE_DIR,env=env,timeout=240)
        self.assertEqual(result.returncode,0)
