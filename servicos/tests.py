from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient
from empresa.models import Empresa
from usuario.models import Usuario
from clientes.models import Cliente,Uf
from .models import Servico

class ServiceAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Empresa.objects.create(cnpj='1',razao='Empresa Alfa');cls.other=Empresa.objects.create(cnpj='2',razao='Empresa Beta')
        cls.uf=Uf.objects.create(sigla='CE',descricao='Ceará');cls.other_uf=Uf.objects.create(sigla='PI',descricao='Piauí')
        cls.customer=Cliente.objects.create(empresa=cls.company,instituicao='Cliente Alfa',uf=cls.uf)
        cls.foreign_customer=Cliente.objects.create(empresa=cls.other,instituicao='Cliente Beta',uf=cls.uf)
        cls.restricted_customer=Cliente.objects.create(empresa=cls.company,instituicao='Cliente PI',uf=cls.other_uf)
        cls.user=Usuario.objects.create_user(username='servicos_test',email='servicos@example.test',password='test');cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='servicos'))
        cls.service=Servico.objects.create(empresa=cls.company,cliente=cls.customer,descricao='Serviço Alfa',usuario=cls.user)
        cls.foreign_service=Servico.objects.create(empresa=cls.other,cliente=cls.foreign_customer,descricao='Serviço Beta',usuario=cls.user)
    def setUp(self):
        self.client=APIClient();self.client.force_authenticate(self.user);self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))
    def url(self,pk=None):return '/servico/api/servicos/'+(str(pk)+'/' if pk else '')
    def test_auth_company_and_foreign_object_mutations(self):
        self.client.force_authenticate(None);self.assertEqual(self.client.get(self.url()).status_code,401)
        self.client.force_authenticate(self.user);self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))
        for method in ['get','delete']:
            self.assertEqual(getattr(self.client,method)(self.url(self.foreign_service.pk)).status_code,404)
        self.assertEqual(self.client.patch(self.url(self.foreign_service.pk),{'descricao':'Mudou'},format='json').status_code,404)
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.other.pk));self.assertEqual(self.client.get(self.url()).status_code,403)
    def test_crud_actor_company_readonly_and_filter(self):
        response=self.client.post(self.url(),{'cliente':self.customer.pk,'descricao':'Novo serviço','empresa':self.other.pk,'usuario':999},format='json');self.assertEqual(response.status_code,201,response.data)
        obj=Servico.objects.get(pk=response.data['id']);self.assertEqual(obj.empresa_id,self.company.pk);self.assertEqual(obj.usuario_id,self.user.pk)
        response=self.client.patch(self.url(obj.pk),{'descricao':'Editado'},format='json');self.assertEqual(response.status_code,200,response.data)
        response=self.client.get(self.url(),{'search':'Editado','cliente':self.customer.pk});self.assertEqual(response.data['count'],1)
        self.assertEqual(self.client.delete(self.url(obj.pk)).status_code,204)
    def test_invalid_customer_description_and_global_unique_preserved(self):
        for values in [{'cliente':self.foreign_customer.pk,'descricao':'Novo'},{'cliente':self.customer.pk,'descricao':' '},{'cliente':self.customer.pk,'descricao':'Serviço Beta'},{'cliente':self.customer.pk,'descricao':'X'*101}]:
            response=self.client.post(self.url(),values,format='json');self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(Servico.objects.count(),2)
    def test_uf_scope_applies_to_options_list_and_writes(self):
        self.user.uf=self.uf;self.user.save()
        hidden=Servico.objects.create(empresa=self.company,cliente=self.restricted_customer,descricao='Oculto')
        self.assertEqual(self.client.get(self.url()).data['count'],1)
        self.assertEqual(self.client.get(self.url(hidden.pk)).status_code,404)
        self.assertEqual(self.client.get('/servico/api/opcoes/').data['count'],1)
        self.assertEqual(self.client.patch(self.url(self.service.pk),{'cliente':self.restricted_customer.pk},format='json').status_code,400)
    def test_service_only_operator_options_without_client_permissions(self):
        response=self.client.get('/servico/api/opcoes/',{'id':self.customer.pk});self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['results'],[{'id':self.customer.pk,'instituicao':'Cliente Alfa'}])
        self.assertEqual(self.client.get('/servico/api/opcoes/',{'id':self.foreign_customer.pk}).data['count'],0)
    def test_readonly_role_and_session_csrf(self):
        reader=Usuario.objects.create_user(username='servicos_reader',email='reader@example.test',password='test');reader.empresas.add(self.company)
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='servicos',codename='view_servico'))
        self.client.force_authenticate(reader);self.assertEqual(self.client.get(self.url()).status_code,200)
        self.assertEqual(self.client.post(self.url(),{},format='json').status_code,403)
        self.assertEqual(self.client.patch(self.url(self.service.pk),{},format='json').status_code,403)
        self.assertEqual(self.client.delete(self.url(self.service.pk)).status_code,403)
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url(),{},format='json').status_code,403)
    def test_legacy_redirect_and_http_methods(self):
        self.assertEqual(self.client.get('/servico/list/').url,'/clientes/app/servicos')
        self.assertEqual(self.client.get(f'/servico/delete_servico/{self.service.pk}/').status_code,405)
        self.assertEqual(self.client.post(f'/servico/delete_servico/{self.service.pk}/').status_code,405)
        self.assertTrue(Servico.objects.filter(pk=self.service.pk).exists())
