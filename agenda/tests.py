from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient
from empresa.models import Empresa
from usuario.models import Usuario
from clientes.models import Cliente,Uf,Municipio
from .models import Contato,Email,Telefone

class AgendaAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Empresa.objects.create(cnpj='1',razao='Empresa Alfa');cls.other=Empresa.objects.create(cnpj='2',razao='Empresa Beta')
        cls.uf=Uf.objects.create(sigla='CE',descricao='Ceará');cls.other_uf=Uf.objects.create(sigla='PI',descricao='Piauí')
        cls.city=Municipio.objects.create(uf=cls.uf,descricao='Fortaleza',codigo_ibge='2304400')
        cls.customer=Cliente.objects.create(empresa=cls.company,instituicao='Cliente Alfa',uf=cls.uf)
        cls.foreign_customer=Cliente.objects.create(empresa=cls.other,instituicao='Cliente Beta',uf=cls.uf)
        cls.hidden_customer=Cliente.objects.create(empresa=cls.company,instituicao='Cliente PI',uf=cls.other_uf)
        cls.user=Usuario.objects.create_user(username='agenda_test',email='agenda@example.test',password='test');cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='agenda'))
        cls.contact=Contato.objects.create(cliente=cls.customer,nome='Contato Alfa')
        cls.foreign=Contato.objects.create(cliente=cls.foreign_customer,nome='Contato Beta')
        cls.orphan=Contato.objects.create(nome='Contato sem cliente')
        cls.email=Email.objects.create(contato=cls.contact,email='alfa@example.test')
        cls.phone=Telefone.objects.create(contato=cls.contact,fone='85999990000')
    def setUp(self):
        self.client=APIClient();self.client.force_authenticate(self.user);self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))
    def url(self,pk=None):return '/agenda/api/contatos/'+(str(pk)+'/' if pk else '')
    def values(self,**changes):return {'cliente':self.customer.pk,'nome':'Novo contato','emails':[{'email':'novo@example.test'}],'telefones':[{'fone':'85999991111'}],**changes}
    def test_auth_company_orphans_and_mutations(self):
        self.assertEqual(self.client.get(self.url()).data['count'],1)
        for obj in [self.foreign,self.orphan]:
            self.assertEqual(self.client.get(self.url(obj.pk)).status_code,404)
            self.assertEqual(self.client.patch(self.url(obj.pk),{'nome':'Alterado'},format='json').status_code,404)
            self.assertEqual(self.client.delete(self.url(obj.pk)).status_code,404)
        self.client.force_authenticate(None);self.assertEqual(self.client.get(self.url()).status_code,401)
        self.client.force_authenticate(self.user);self.client.credentials(HTTP_X_EMPRESA_ID=str(self.other.pk));self.assertEqual(self.client.get(self.url()).status_code,403)
    def test_nested_create_update_preserves_ids_and_omitted_lists(self):
        response=self.client.post(self.url(),self.values(),format='json');self.assertEqual(response.status_code,201,response.data)
        pk=response.data['id'];email_id=response.data['emails'][0]['id'];phone_id=response.data['telefones'][0]['id']
        response=self.client.patch(self.url(pk),{'nome':'Editado','emails':[{'id':email_id,'email':'editado@example.test'}]},format='json');self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['emails'][0]['id'],email_id);self.assertEqual(response.data['telefones'][0]['id'],phone_id)
        self.assertEqual(self.client.delete(self.url(pk)).status_code,204)
        self.assertFalse(Email.objects.filter(pk=email_id).exists());self.assertFalse(Telefone.objects.filter(pk=phone_id).exists())
    def test_invalid_fields_duplicate_values_and_foreign_customer(self):
        for changes in [{'cliente':self.foreign_customer.pk},{'cliente':None},{'nome':' '},{'emails':[{'email':'bad'}]},{'telefones':[{'fone':'abcd'}]},{'emails':[{'email':'same@example.test'},{'email':'SAME@example.test'}]},{'cidade':self.city.pk,'uf':self.other_uf.pk}]:
            response=self.client.post(self.url(),self.values(**changes),format='json');self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(Contato.objects.count(),3)
    def test_child_id_must_belong_to_contact_and_rollback(self):
        foreign_email=Email.objects.create(contato=self.foreign,email='beta@example.test')
        response=self.client.patch(self.url(self.contact.pk),{'nome':'Não deve persistir','emails':[{'id':foreign_email.pk,'email':'roubo@example.test'}]},format='json')
        self.assertEqual(response.status_code,400,response.data);self.contact.refresh_from_db();self.assertEqual(self.contact.nome,'Contato Alfa');self.assertTrue(Email.objects.filter(pk=self.email.pk).exists())
    def test_nested_permission_failure_rolls_back_parent_and_all_children(self):
        user=Usuario.objects.create_user(username='agenda_editor',email='editor@example.test',password='test');user.empresas.add(self.company)
        user.user_permissions.set(Permission.objects.filter(content_type__app_label='agenda').exclude(codename='add_telefone'))
        self.client.force_authenticate(user)
        response=self.client.post(self.url(),self.values(),format='json');self.assertEqual(response.status_code,403,response.data)
        self.assertEqual(Contato.objects.count(),3);self.assertEqual(Email.objects.count(),1)
    def test_nested_visibility_and_edit_permissions(self):
        user=Usuario.objects.create_user(username='agenda_reader',email='reader@example.test',password='test');user.empresas.add(self.company)
        user.user_permissions.set(Permission.objects.filter(content_type__app_label='agenda',codename__in=['view_contato','change_contato','delete_contato']))
        self.client.force_authenticate(user)
        response=self.client.get(self.url(self.contact.pk));self.assertNotIn('emails',response.data);self.assertNotIn('telefones',response.data)
        self.assertEqual(self.client.patch(self.url(self.contact.pk),{'emails':[]},format='json').status_code,403)
        self.assertEqual(self.client.delete(self.url(self.contact.pk)).status_code,403)
        self.assertTrue(Email.objects.filter(pk=self.email.pk).exists());self.assertTrue(Contato.objects.filter(pk=self.contact.pk).exists())
    def test_uf_scope_options_and_filter(self):
        self.user.uf=self.uf;self.user.save();hidden=Contato.objects.create(cliente=self.hidden_customer,nome='Contato PI')
        self.assertEqual(self.client.get(self.url(hidden.pk)).status_code,404)
        response=self.client.get('/agenda/api/opcoes/');self.assertEqual(response.data['count'],1)
        response=self.client.get(self.url(),{'search':'Alfa','cliente':self.customer.pk});self.assertEqual(response.data['count'],1)
    def test_csrf_and_legacy(self):
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url(),self.values(),format='json').status_code,403)
        self.assertEqual(self.client.get('/agenda/list/').url,'/clientes/app/agenda')
        self.assertEqual(self.client.get('/agenda/new/').status_code,405)
    def test_partial_nested_missing_value_is_validation_error(self):
        self.assertEqual(self.client.patch(self.url(self.contact.pk),{'emails':[{'id':self.email.pk}]},format='json').status_code,400)
        self.assertEqual(self.client.patch(self.url(self.contact.pk),{'telefones':[{'id':self.phone.pk}]},format='json').status_code,400)
