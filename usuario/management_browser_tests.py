import os
import subprocess
import tempfile
import types
from pathlib import Path
from PIL import Image
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from django.urls import get_resolver, re_path
from django.views.static import serve
from . import test_management as fixtures


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class CadastroUsuarioBrowserTests(StaticLiveServerTestCase):
    def test_user_registration_and_header(self):
        cache.clear()
        fixtures.CadastroUsuarioTests.setUpTestData.__func__(type(self))
        media = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(self.settings(MEDIA_ROOT=media))
        urls = types.ModuleType('usuario_management_e2e_urls')
        urls.urlpatterns = [re_path(r'^media/(?P<path>.*)$', serve, {'document_root': media}), *get_resolver().url_patterns]
        self.enterContext(self.settings(ROOT_URLCONF=urls))
        directory = Path('/tmp/gestao-users-e2e'); directory.mkdir(exist_ok=True)
        image = directory / 'avatar.png'; Image.new('RGB', (96, 96), '#bd252a').save(image)
        env = {**os.environ, 'E2E_BASE_URL': self.live_server_url, 'E2E_USERNAME': self.actor.username, 'E2E_PASSWORD': fixtures.PASSWORD,
               'E2E_AVATAR_PATH': str(image), 'PLAYWRIGHT_BROWSERS_PATH': '/tmp/gestao-playwright'}
        result = subprocess.run(['node_modules/.bin/playwright', 'test', 'users.spec.ts'], cwd=settings.BASE_DIR, env=env, timeout=240)
        self.assertEqual(result.returncode, 0)
