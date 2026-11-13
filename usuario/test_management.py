from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from clientes.models import Uf
from empresa.models import Empresa
from .models import Usuario

PASSWORD = 'Account-test-passphrase-813!'
URL = '/usuario/api/usuarios/'


class CadastroUsuarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Empresa.objects.create(cnpj='1', razao='Empresa Alfa')
        cls.b = Empresa.objects.create(cnpj='2', razao='Empresa Beta')
        cls.outside = Empresa.objects.create(cnpj='3', razao='Empresa externa')
        cls.uf = Uf.objects.create(sigla='CE', descricao='Ceará')
        cls.actor = Usuario.objects.create_user(username='manager', email='manager@example.test', password=PASSWORD, uf=cls.uf)
        cls.actor.empresas.add(cls.a, cls.b)
        cls.add = Permission.objects.get(content_type__app_label='usuario', codename='add_usuario')
        cls.view = Permission.objects.get(content_type__app_label='usuario', codename='view_usuario')
        cls.clients = Permission.objects.get(content_type__app_label='clientes', codename='view_cliente')
        cls.actor.user_permissions.add(cls.add, cls.clients)

    def setUp(self):
        cache.clear()
        self.client = APIClient(HTTP_X_EMPRESA_ID=str(self.a.pk))
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(self.actor)))

    def payload(self, **values):
        return {'username': 'new_account', 'first_name': 'Nova pessoa', 'email': 'new@example.test', 'password': PASSWORD, 'conf_password': PASSWORD, 'empresas': [self.a.pk], 'permissoes': [self.clients.pk], **values}

    def create(self, **values):
        return self.client.post(URL, self.payload(**values), format='json')

    def test_requires_authentication_and_explicit_permission(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)
        self.actor.user_permissions.clear()
        self.assertEqual(self.create().status_code, 403)
        self.assertEqual(self.client.get(URL, {'empresa': self.a.pk}).status_code, 403)

    def test_creates_ordinary_account_with_password_hash_and_audit(self):
        from auditlog.models import LogEntry
        response = self.create(empresas=[self.a.pk, self.b.pk])
        self.assertEqual(response.status_code, 201, response.data)
        user = Usuario.objects.get(username='new_account')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertFalse(user.is_staff); self.assertFalse(user.is_superuser)
        self.assertEqual(user.uf_id, self.uf.pk)
        self.assertSetEqual(set(user.empresas.values_list('pk', flat=True)), {self.a.pk, self.b.pk})
        self.assertTrue(user.has_perm('clientes.view_cliente'))
        self.assertFalse(user.has_perm('usuario.add_usuario'))
        for key in ['password', 'conf_password', 'is_staff', 'is_superuser', 'groups']:
            self.assertNotIn(key, response.data)
        entry = LogEntry.objects.get(object_pk=str(user.pk), action=LogEntry.Action.CREATE)
        self.assertEqual(entry.actor_id, self.actor.pk)
        self.assertNotIn(PASSWORD, str(entry.changes))
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_cannot_assign_unknown_or_external_company_or_empty_scope(self):
        for companies in [[self.outside.pk], [self.a.pk, self.outside.pk], [], [999999]]:
            response = self.create(empresas=companies)
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Usuario.objects.filter(username='new_account').exists())

    def test_cannot_delegate_unowned_or_administrative_permissions(self):
        unowned = Permission.objects.get(content_type__app_label='clientes', codename='delete_cliente')
        create_company = Permission.objects.get(content_type__app_label='empresa', codename='add_empresa')
        self.actor.user_permissions.add(create_company)
        for permission in [unowned, self.add, create_company]:
            response = self.create(permissoes=[permission.pk])
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Usuario.objects.filter(username='new_account').exists())

    def test_privileged_payload_fields_are_rejected(self):
        for values in [{'is_superuser': True}, {'is_staff': True}, {'is_active': False}, {'groups': [1]}, {'user_permissions': [self.add.pk]}, {'uf': self.uf.pk}, {'id': self.actor.pk}]:
            response = self.create(**values)
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Usuario.objects.filter(username='new_account').exists())

    def test_password_and_identity_validation(self):
        for values in [{'password': 'short', 'conf_password': 'short'}, {'conf_password': 'different'}, {'username': 'bad user'}, {'username': self.actor.username.upper()}, {'email': self.actor.email.upper()}, {'email': 'invalid'}]:
            response = self.create(**values)
            self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Usuario.objects.filter(username='new_account').exists())

    def test_list_hides_admins_and_accounts_with_any_outside_company(self):
        inside = Usuario.objects.create_user(username='inside', email='inside@example.test', password=PASSWORD)
        inside.empresas.add(self.a, self.b)
        mixed = Usuario.objects.create_user(username='mixed', email='mixed@example.test', password=PASSWORD)
        mixed.empresas.add(self.a, self.outside)
        admin = Usuario.objects.create_superuser(username='admin_test', email='admin@example.test', password=PASSWORD)
        admin.empresas.add(self.a)
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('inside', [row['username'] for row in response.data['results']])
        self.assertNotIn('mixed', [row['username'] for row in response.data['results']])
        self.assertNotIn('admin_test', [row['username'] for row in response.data['results']])
        self.assertEqual(self.client.get(URL, HTTP_X_EMPRESA_ID=str(self.outside.pk)).status_code, 403)

    def test_options_limit_companies_permissions_and_keep_profile_private(self):
        response = self.client.get(URL + 'opcoes/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertSetEqual({row['id'] for row in response.data['empresas']}, {self.a.pk, self.b.pk})
        self.assertEqual([row['id'] for row in response.data['permissoes']], [self.clients.pk])
        self.assertEqual(self.client.patch(URL + str(self.actor.pk) + '/', {'first_name': 'changed'}, format='json').status_code, 404)
        self.assertEqual(self.client.get(f'/usuario/edit/{self.actor.pk + 999}/').status_code, 404)

    def test_view_permission_cannot_create(self):
        self.actor.user_permissions.set([self.view])
        self.assertEqual(self.client.get(URL).status_code, 200)
        self.assertEqual(self.create().status_code, 403)

    def test_audit_failure_rolls_back_user_and_links(self):
        with patch('auditlog.models.LogEntry.objects.log_create', side_effect=RuntimeError('test rollback')):
            with self.assertRaises(RuntimeError):
                self.create()
        self.assertFalse(Usuario.objects.filter(username='new_account').exists())

    def test_new_account_cannot_access_unassigned_company(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        user = Usuario.objects.get(pk=response.data['id'])
        client = APIClient(); client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(AccessToken.for_user(user)))
        self.assertEqual(client.get('/clientes/api/clientes/', HTTP_X_EMPRESA_ID=str(self.a.pk)).status_code, 200)
        self.assertEqual(client.get('/clientes/api/clientes/', HTTP_X_EMPRESA_ID=str(self.b.pk)).status_code, 403)
        self.assertEqual(client.get('/usuario/api/usuarios/', HTTP_X_EMPRESA_ID=str(self.a.pk)).status_code, 403)

    def test_me_exposes_only_own_avatar(self):
        response = self.client.get('/clientes/api/auth/me/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['avatar'])
        self.actor.avatar = 'avatar/example.png'; self.actor.save(update_fields=['avatar'])
        response = self.client.get('/clientes/api/auth/me/')
        self.assertTrue(response.data['avatar'].endswith('/media/avatar/example.png'))
