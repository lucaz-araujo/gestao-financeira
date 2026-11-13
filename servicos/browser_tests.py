import os
import subprocess
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from . import tests as fixtures
@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class ServiceBrowserTests(StaticLiveServerTestCase):
    def test_services_frontend(self):
        cache.clear();fixtures.ServiceAPITests.setUpTestData.__func__(type(self))
        env={**os.environ,'E2E_BASE_URL':self.live_server_url,'E2E_USERNAME':self.user.username,'E2E_PASSWORD':'test','PLAYWRIGHT_BROWSERS_PATH':'/tmp/gestao-playwright'}
        result=subprocess.run(['node_modules/.bin/playwright','test','servicos.spec.ts'],cwd=settings.BASE_DIR,env=env,timeout=180)
        self.assertEqual(result.returncode,0)
