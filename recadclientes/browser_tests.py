import os
from pathlib import Path
import subprocess
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from usuario.models import Usuario
from . import tests as fixtures


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class RecadBrowserTests(StaticLiveServerTestCase):
    def test_recad_frontend(self):
        cache.clear();fixtures.RecadAPITests.setUpTestData.__func__(type(self))
        self.user.uf=self.uf;self.user.save(update_fields=['uf']);self.user.empresas.add(self.other)
        reader=Usuario.objects.create_user(username='recad_reader',email='recad-reader@example.test',password='Recad-test-passphrase-918!')
        reader.empresas.add(self.company);reader.user_permissions.add(Permission.objects.get(content_type__app_label='recadclientes',codename='view_entidaderecad'))
        child_reader=Usuario.objects.create_user(username='recad_child',email='recad-child@example.test',password='Recad-test-passphrase-918!')
        child_reader.empresas.add(self.company);child_reader.user_permissions.add(Permission.objects.get(content_type__app_label='recadclientes',codename='view_contadorrecad'))
        fixtures.ContadorRecad.objects.create(entidade=self.entity,nome_completo='Contador de teste')
        Path('/tmp/gestao-recad-e2e').mkdir(exist_ok=True)
        env={**os.environ,'E2E_BASE_URL':self.live_server_url,'E2E_USERNAME':self.user.username,'E2E_READER_USERNAME':reader.username,'E2E_CHILD_USERNAME':child_reader.username,'E2E_PASSWORD':'Recad-test-passphrase-918!','PLAYWRIGHT_BROWSERS_PATH':'/tmp/gestao-playwright'}
        result=subprocess.run(['node_modules/.bin/playwright','test','recad.spec.ts'],cwd=settings.BASE_DIR,env=env,timeout=240)
        self.assertEqual(result.returncode,0)
