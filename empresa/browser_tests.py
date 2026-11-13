import os
import subprocess
import tempfile
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from usuario.models import Usuario
from . import tests as fixtures
@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class EmpresaBrowserTests(StaticLiveServerTestCase):
    def test_companies_frontend(self):
        cache.clear();fixtures.EmpresaAPITests.setUpTestData.__func__(type(self))
        media=self.enterContext(tempfile.TemporaryDirectory());self.enterContext(self.settings(MEDIA_ROOT=media))
        logo=fixtures.EmpresaAPITests.image(self);source=Path(media)/'source.png';source.write_bytes(logo.read())
        reader=Usuario.objects.create_user(username='empresa_reader',email='reader@example.test',password='test');reader.empresas.add(self.company)
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='empresa',codename='view_empresa'))
        creator=Usuario.objects.create_user(username='empresa_creator',email='creator@example.test',password='test')
        creator.user_permissions.add(Permission.objects.get(content_type__app_label='empresa',codename='add_empresa'))
        env={**os.environ,'E2E_BASE_URL':self.live_server_url,'E2E_USERNAME':self.user.username,'E2E_READER_USERNAME':reader.username,'E2E_CREATOR_USERNAME':creator.username,'E2E_PASSWORD':'test','E2E_CNPJ':fixtures.cnpj('345678900001'),'E2E_CREATOR_CNPJ':fixtures.cnpj('456789010001'),'E2E_LOGO_PATH':str(source),'PLAYWRIGHT_BROWSERS_PATH':'/tmp/gestao-playwright'}
        result=subprocess.run(['node_modules/.bin/playwright','test','empresa.spec.ts'],cwd=settings.BASE_DIR,env=env,timeout=240)
        self.assertEqual(result.returncode,0)
