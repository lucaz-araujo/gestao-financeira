import os
import subprocess
from pathlib import Path
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.core.cache import cache
from . import tests as fixtures


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class FinanceiroBrowserTests(StaticLiveServerTestCase):
    def test_financial_frontend(self):
        cache.clear()
        fixtures.FinanceiroAPITests.setUpTestData.__func__(type(self))
        screenshots = '/tmp/gestao-financeiro-e2e'
        Path(screenshots).mkdir(exist_ok=True)
        env = {**os.environ, 'E2E_BASE_URL': self.live_server_url, 'E2E_USERNAME': self.user.username,
               'E2E_PASSWORD': 'test', 'E2E_SCREENSHOT_DIR': screenshots,
               'PLAYWRIGHT_BROWSERS_PATH': '/tmp/gestao-playwright'}
        result = subprocess.run(['node_modules/.bin/playwright', 'test', 'financeiro.spec.ts'],
                                cwd=settings.BASE_DIR, env=env, timeout=240)
        self.assertEqual(result.returncode, 0)
