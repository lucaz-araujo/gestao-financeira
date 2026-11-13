from django.test import TestCase
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient
from empresa.models import Empresa
from usuario.models import Usuario
from .models import PlanoContas, CentroCusto, TipoDespesa, Lancamentos

class AccountingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Empresa.objects.create(cnpj='1',razao='Alfa')
        cls.other=Empresa.objects.create(cnpj='2',razao='Beta')
        cls.user=Usuario.objects.create_user(username='contabil_test',email='contabil@example.test',password='test')
        cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='contabil'))
        cls.a=PlanoContas.objects.create(empresa=cls.company,conta='1',descricao='Plano A')
        cls.b=PlanoContas.objects.create(empresa=cls.company,conta='2',descricao='Plano B')
        cls.foreign=PlanoContas.objects.create(empresa=cls.other,conta='3',descricao='Plano estrangeiro')
        cls.shared=TipoDespesa.objects.create(codigo='000',descricao='Compartilhado')
    def setUp(self):
        self.client=APIClient();self.client.force_authenticate(self.user);self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))
    def url(self,resource,pk=None): return '/contabil/api/'+resource+'/'+(str(pk)+'/' if pk else '')
    def post(self,resource,data): return self.client.post(self.url(resource),data,format='json')
    def test_auth_and_company(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url('planos')).status_code,401)
        self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))
        self.assertEqual(self.client.get(self.url('planos')).data['count'],2)
        self.assertEqual(self.client.get(self.url('planos',self.foreign.pk)).status_code,404)
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.other.pk))
        self.assertEqual(self.client.get(self.url('planos')).status_code,403)
    def test_create_update_duplicates_and_readonly_company(self):
        data={'conta':'001.1','descricao':'Nova','codigo':'00001','empresa':self.other.pk}
        response=self.post('planos',data);self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(PlanoContas.objects.get(pk=response.data['id']).empresa_id,self.company.pk)
        self.assertEqual(self.post('planos',data).status_code,400)
        self.assertEqual(self.client.patch(self.url('planos',response.data['id']),{'descricao':'Editado'},format='json').status_code,200)
    def test_center_company_and_protected_plan(self):
        data={'codigo':'001','descricao':'Centro','conta':self.foreign.pk}
        self.assertEqual(self.post('centros',data).status_code,400)
        response=self.post('centros',{**data,'conta':self.a.pk});self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(self.client.delete(self.url('planos',self.a.pk)).status_code,409)
        self.assertEqual(self.client.delete(self.url('centros',response.data['id'])).status_code,204)
    def test_shared_catalog_is_readonly_and_scoped_types(self):
        self.assertEqual(self.client.get(self.url('tipos')).data['count'],1)
        self.assertEqual(self.client.patch(self.url('tipos',self.shared.pk),{'descricao':'Mudou','conta':self.a.pk},format='json').status_code,409)
        self.assertEqual(self.client.delete(self.url('tipos',self.shared.pk)).status_code,409)
        self.assertEqual(self.post('tipos',{'codigo':'001','descricao':'Sem plano'}).status_code,400)
        response=self.post('tipos',{'codigo':'001','descricao':'Tipo A','conta':self.a.pk});self.assertEqual(response.status_code,201,response.data)
        TipoDespesa.objects.create(codigo='002',descricao='Tipo Beta',conta=self.foreign)
        self.assertEqual(self.client.get(self.url('tipos')).data['count'],2)
        self.assertEqual(self.client.patch(self.url('tipos',response.data['id']),{'conta':self.b.pk},format='json').status_code,400)
    def test_ledger_validations_scope_and_crud(self):
        values={'dt_data':'2026-11-04T12:00:00-03:00','tipo':'C','conta_origem':self.a.pk,'conta_destino':self.b.pk,'valor':'12.34','descricao':'Teste'}
        for changes in [{'conta_destino':self.foreign.pk},{'conta_destino':self.a.pk},{'valor':'0'},{'valor':'1.001'},{'dt_data':None}]:
            self.assertEqual(self.post('lancamentos',{**values,**changes}).status_code,400)
        response=self.post('lancamentos',values);self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(self.client.patch(self.url('lancamentos',response.data['id']),{'valor':'20.00'},format='json').status_code,200)
        Lancamentos.objects.create(conta_origem=self.a,conta_destino=self.foreign,valor=10)
        self.assertEqual(self.client.get(self.url('lancamentos')).data['count'],1)
        self.assertEqual(self.client.delete(self.url('lancamentos',response.data['id'])).status_code,204)
    def test_readonly_role_and_legacy(self):
        reader=Usuario.objects.create_user(username='reader_conta',email='reader@example.test',password='test');reader.empresas.add(self.company)
        reader.user_permissions.set(Permission.objects.filter(content_type__app_label='contabil',codename__startswith='view_'))
        self.client.force_authenticate(reader)
        for resource in ['planos','centros','tipos','lancamentos']:
            self.assertEqual(self.client.get(self.url(resource)).status_code,200)
            self.assertEqual(self.post(resource,{}).status_code,403)
        self.assertEqual(self.client.get('/contabil/list_plconta/').url,'/clientes/app/contabil-planos')
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url('planos'),{},format='json').status_code,403)

    def test_options_available_without_plan_view_permission(self):
        user=Usuario.objects.create_user(username='centro_editor',email='centro@example.test',password='test')
        user.empresas.add(self.company)
        user.user_permissions.add(Permission.objects.get(content_type__app_label='contabil',codename='add_centrocusto'))
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(self.url('planos')).status_code,403)
        response=self.client.get(self.url('opcoes'))
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['count'],2)
