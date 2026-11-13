import os
import subprocess
from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import override_settings
from usuario.models import Usuario
from . import tests as fixtures


@override_settings(CLIENTES_AUTH_COOKIE_SECURE=False)
class DashboardBrowserTests(StaticLiveServerTestCase):
    def test_dashboard_frontend(self):
        cache.clear()
        fixtures.DashboardAPITests.setUpTestData.__func__(type(self))
        self.user.uf = self.uf
        self.user.save(update_fields=['uf'])
        reader = Usuario.objects.create_user(username='dash_reader', email='dash-reader@example.test', password='Dashboard-test-918!', ultimo_mes=11, ultimo_ano=2026)
        reader.empresas.add(self.company)
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='notas', codename='view_nota'))
        no_access = Usuario.objects.create_user(username='dash_profile', email='dash-profile@example.test', password='Dashboard-test-918!')
        no_access.empresas.add(self.company)
        Path('/tmp/gestao-dashboard-e2e').mkdir(exist_ok=True)
        env = {**os.environ, 'E2E_BASE_URL': self.live_server_url, 'E2E_USERNAME': self.user.username,
               'E2E_READER_USERNAME': reader.username, 'E2E_PROFILE_USERNAME': no_access.username,
               'E2E_PASSWORD': 'Dashboard-test-918!', 'PLAYWRIGHT_BROWSERS_PATH': '/tmp/gestao-playwright'}
        with patch('dashboard.services.timezone.localdate', return_value=fixtures.TODAY):
            result = subprocess.run(['node_modules/.bin/playwright', 'test', 'dashboard.spec.ts'], cwd=settings.BASE_DIR, env=env, timeout=240)
        self.assertEqual(result.returncode, 0)
