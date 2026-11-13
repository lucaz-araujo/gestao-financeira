import os
import subprocess
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from empresa.models import Empresa
from usuario.models import Usuario


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class NavigationBrowserTests(StaticLiveServerTestCase):
    def test_legacy_navigation(self):
        cache.clear()
        company=Empresa.objects.create(cnpj='1',razao='Empresa de navegação')
        user=Usuario.objects.create_user(username='nav_full',email='nav-full@example.test',password='Navigation-test-918!')
        user.empresas.add(company);user.user_permissions.set(Permission.objects.all())
        contact=Usuario.objects.create_user(username='nav_contact',email='nav-contact@example.test',password='Navigation-test-918!')
        contact.empresas.add(company);contact.user_permissions.add(Permission.objects.get(content_type__app_label='agenda',codename='view_contato'))
        Path('/tmp/gestao-navigation-e2e').mkdir(exist_ok=True)
        env={**os.environ,'E2E_BASE_URL':self.live_server_url,'E2E_USERNAME':user.username,'E2E_CONTACT_USERNAME':contact.username,'E2E_PASSWORD':'Navigation-test-918!','PLAYWRIGHT_BROWSERS_PATH':'/tmp/gestao-playwright'}
        result=subprocess.run(['node_modules/.bin/playwright','test','navigation.spec.ts'],cwd=settings.BASE_DIR,env=env,timeout=240)
        self.assertEqual(result.returncode,0)
