import os
import tempfile
import subprocess
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.core.cache import cache
from usuario.models import Usuario
from . import tests as fixtures
@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class AmbienteBrowserTests(StaticLiveServerTestCase):
    def test_fiscal_environment_frontend(self):
        cache.clear();fixtures.AmbienteAPITests.setUpTestData.__func__(type(self))
        private=self.enterContext(tempfile.TemporaryDirectory());self.enterContext(self.settings(PRIVATE_CERTIFICATE_ROOT=private))
        source=Path(private)/'synthetic-upload.pfx';source.write_bytes(fixtures.synthetic_certificate())
        reader=Usuario.objects.create_user(username='fiscal_reader',email='reader@example.test',password='test');reader.empresas.add(self.company)
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='configambiente',codename='view_ambiente'))
        env={**os.environ,'E2E_BASE_URL':self.live_server_url,'E2E_USERNAME':self.user.username,'E2E_READER_USERNAME':reader.username,'E2E_PASSWORD':'test','E2E_CERTIFICATE_PATH':str(source),'PLAYWRIGHT_BROWSERS_PATH':'/tmp/gestao-playwright'}
        result=subprocess.run(['node_modules/.bin/playwright','test','ambiente.spec.ts'],cwd=settings.BASE_DIR,env=env,timeout=240)
        self.assertEqual(result.returncode,0)
