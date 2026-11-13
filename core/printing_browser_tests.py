import os
import subprocess
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from financeiro import tests as fixtures


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class PrintingBrowserTests(StaticLiveServerTestCase):
    def test_printed_reports(self):
        cache.clear();fixtures.FinanceiroAPITests.setUpTestData.__func__(type(self))
        self.company.razao='Empresa de demonstração';self.company.cnpj='11.222.333/0001-81';self.company.save()
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='clientes',codename='view_cliente'))
        env={**os.environ,'E2E_BASE_URL':self.live_server_url,'E2E_USERNAME':self.user.username,'E2E_PASSWORD':'test','PLAYWRIGHT_BROWSERS_PATH':'/tmp/gestao-playwright'}
        result=subprocess.run(['node_modules/.bin/playwright','test','printing.spec.ts'],cwd=settings.BASE_DIR,env=env,timeout=240)
        self.assertEqual(result.returncode,0)
