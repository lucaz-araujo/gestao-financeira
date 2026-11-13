from django.contrib.admin.sites import site
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase, RequestFactory, override_settings
from rest_framework.test import APIClient
from clientes.models import Cliente, Uf, Municipio
from empresa.models import Empresa
from usuario.models import Usuario
from .models import EntidadeRecad, UsuarioRecad, ContadorRecad, ControladorRecad, PrefeitoRecad, VicePrefeitoRecad, MODELOS_RECAD

ROLES = [('usuarios',UsuarioRecad), ('contadores',ContadorRecad), ('controladores',ControladorRecad), ('prefeitos',PrefeitoRecad), ('vice-prefeitos',VicePrefeitoRecad)]


class RecadAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Empresa.objects.create(cnpj='1',razao='Empresa Alfa')
        cls.other=Empresa.objects.create(cnpj='2',razao='Empresa Beta')
        cls.uf=Uf.objects.create(sigla='CE',descricao='Ceará')
        cls.other_uf=Uf.objects.create(sigla='PI',descricao='Piauí')
        cls.city=Municipio.objects.create(uf=cls.uf,descricao='Fortaleza',codigo_ibge='2304400')
        cls.foreign_city=Municipio.objects.create(uf=cls.other_uf,descricao='Teresina',codigo_ibge='2211001')
        cls.customer=Cliente.objects.create(empresa=cls.company,instituicao='Cliente Alfa',uf=cls.uf)
        cls.foreign=Cliente.objects.create(empresa=cls.other,instituicao='Cliente Beta',uf=cls.uf)
        cls.hidden=Cliente.objects.create(empresa=cls.company,instituicao='Cliente PI',uf=cls.other_uf)
        cls.user=Usuario.objects.create_user(username='recad_test',email='recad@example.test',password='Recad-test-passphrase-918!')
        cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='recadclientes'))
        cls.entity=EntidadeRecad.objects.create(cliente=cls.customer,nome='Entidade Alfa',uf=cls.uf,cidade=cls.city,email='entidade@example.test')
        cls.foreign_entity=EntidadeRecad.objects.create(cliente=cls.foreign,nome='Entidade Beta')
        cls.hidden_entity=EntidadeRecad.objects.create(cliente=cls.hidden,nome='Entidade PI')
        cls.person=UsuarioRecad.objects.create(entidade=cls.entity,nome_completo='Pessoa Alfa',cargo='Responsável',email='pessoa@example.test')
        cls.foreign_person=UsuarioRecad.objects.create(entidade=cls.foreign_entity,nome_completo='Pessoa Beta')
        cls.hidden_person=UsuarioRecad.objects.create(entidade=cls.hidden_entity,nome_completo='Pessoa PI')

    def setUp(self):
        self.client=APIClient();self.client.force_authenticate(self.user)
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))

    def url(self,resource='entidades',pk=None):return '/recadclientes/api/'+resource+'/'+(str(pk)+'/' if pk else '')
    def values(self,**changes):return {'cliente':self.customer.pk,'nome':'Nova entidade','codigo':'001','tipo':'PREF','uf':self.uf.pk,'cidade':self.city.pk,'telefone':'85999991111','email':'novo@example.test','site':'https://example.test',**changes}
    def perms(self,*names):
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='recadclientes',codename__in=names))
        self.user=Usuario.objects.get(pk=self.user.pk);self.client.force_authenticate(self.user)

    def test_auth_company_and_uf_scope_for_entities_and_people(self):
        self.user.uf=self.uf;self.user.save(update_fields=['uf'])
        self.assertEqual(self.client.get(self.url()).data['count'],1)
        self.assertEqual(self.client.get(self.url('usuarios')).data['count'],1)
        for obj in [self.foreign_entity,self.hidden_entity]:
            for method,data in [('get',{}),('patch',{'nome':'Alterado'}),('delete',{})]:
                self.assertEqual(getattr(self.client,method)(self.url(pk=obj.pk),data,format='json').status_code,404)
        for obj in [self.foreign_person,self.hidden_person]:
            self.assertEqual(self.client.get(self.url('usuarios',obj.pk)).status_code,404)
            self.assertEqual(self.client.patch(self.url('usuarios',obj.pk),{'nome_completo':'Alterado'},format='json').status_code,404)
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.other.pk));self.assertEqual(self.client.get(self.url()).status_code,403)
        self.client.force_authenticate(None);self.assertEqual(self.client.get(self.url()).status_code,401)

    def test_entity_crud_and_omitted_optional_fields(self):
        response=self.client.post(self.url(),self.values(),format='json');self.assertEqual(response.status_code,201,response.data)
        pk=response.data['id'];self.assertEqual(response.data['cliente_nome'],'Cliente Alfa')
        response=self.client.patch(self.url(pk=pk),{'nome':'Editada','email':None},format='json');self.assertEqual(response.status_code,200,response.data)
        obj=EntidadeRecad.objects.get(pk=pk);self.assertEqual(obj.telefone,'85999991111');self.assertIsNone(obj.email)
        self.assertEqual(self.client.delete(self.url(pk=pk)).status_code,204)

    def test_entity_validation_and_customer_cannot_be_transferred(self):
        for values in [{'nome':' '},{'cliente':None},{'telefone':'abc'},{'telefone':'123'},{'email':'bad'},{'site':'javascript:alert(1)'},{'uf':self.uf.pk,'cidade':self.foreign_city.pk},{'uf':None,'cidade':self.city.pk},{'codigo':'12345'}]:
            response=self.client.post(self.url(),self.values(**values),format='json');self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(self.client.post(self.url(),self.values(cliente=self.foreign.pk),format='json').status_code,400)
        response=self.client.patch(self.url(pk=self.entity.pk),{'cliente':self.hidden.pk},format='json')
        self.assertEqual(response.status_code,400,response.data);self.entity.refresh_from_db();self.assertEqual(self.entity.cliente_id,self.customer.pk)

    def test_all_five_roles_have_crud_and_their_own_fields(self):
        for resource,model in ROLES:
            response=self.client.post(self.url(resource),{'entidade':self.entity.pk,'nome_completo':'Novo responsável','email':'responsavel@example.test','telefone':'85999991111',**({'cargo':'Operador'} if model==UsuarioRecad else {})},format='json')
            self.assertEqual(response.status_code,201,response.data);pk=response.data['id']
            self.assertEqual(response.data['entidade_nome'],'Entidade Alfa')
            self.assertEqual('cargo' in response.data,model==UsuarioRecad)
            response=self.client.patch(self.url(resource,pk),{'nome_completo':'Atualizado'},format='json');self.assertEqual(response.status_code,200,response.data)
            self.assertEqual(model.objects.get(pk=pk).nome_completo,'Atualizado')
            self.assertEqual(self.client.delete(self.url(resource,pk)).status_code,204)

    def test_child_cannot_reference_foreign_or_hidden_entity(self):
        self.user.uf=self.uf;self.user.save(update_fields=['uf'])
        for resource,model in ROLES:
            for entity in [self.foreign_entity,self.hidden_entity]:
                response=self.client.post(self.url(resource),{'entidade':entity.pk,'nome_completo':'Invasão'},format='json');self.assertEqual(response.status_code,400,response.data)
            for data in [{'nome_completo':' '},{'email':'bad'},{'telefone':'invalid'}]:
                response=self.client.post(self.url(resource),{'entidade':self.entity.pk,'nome_completo':'Teste',**data},format='json');self.assertEqual(response.status_code,400,response.data)

    def test_permissions_per_role_do_not_require_parent_view_or_allow_other_models(self):
        self.perms('view_usuariorecad','add_usuariorecad')
        self.assertEqual(self.client.get(self.url('usuarios')).status_code,200)
        self.assertEqual(self.client.get(self.url()).status_code,403)
        self.assertEqual(self.client.get(self.url('contadores')).status_code,403)
        response=self.client.post(self.url('usuarios'),{'entidade':self.entity.pk,'nome_completo':'Permitido'},format='json');self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(self.client.patch(self.url('usuarios',self.person.pk),{'nome_completo':'Não'},format='json').status_code,403)
        self.assertEqual(self.client.delete(self.url('usuarios',self.person.pk)).status_code,403)
        self.assertEqual(self.client.get('/recadclientes/api/opcoes/',{'tipo':'entidades'}).status_code,200)
        self.assertEqual(self.client.get('/recadclientes/api/opcoes/',{'tipo':'clientes'}).status_code,403)

    def test_entity_response_does_not_include_personal_contacts_without_role_permissions(self):
        self.perms('view_entidaderecad')
        data=self.client.get(self.url(pk=self.entity.pk)).data
        self.assertNotIn('usuarios',data);self.assertNotIn('pessoa@example.test',str(data))
        self.assertEqual(self.client.get(self.url('usuarios')).status_code,403)

    def test_entity_deletion_is_protected_with_all_roles(self):
        for resource,model in ROLES:
            if model!=UsuarioRecad:model.objects.create(entidade=self.entity,nome_completo='Preservado')
        response=self.client.delete(self.url(pk=self.entity.pk));self.assertEqual(response.status_code,409,response.data)
        self.assertTrue(EntidadeRecad.objects.filter(pk=self.entity.pk).exists())
        for _,model in ROLES:self.assertTrue(model.objects.filter(entidade=self.entity).exists())

    def test_options_scope_search_filters_and_pagination(self):
        self.user.uf=self.uf;self.user.save(update_fields=['uf'])
        for kind in ['clientes','entidades']:
            response=self.client.get('/recadclientes/api/opcoes/',{'tipo':kind});self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['count'],1)
            foreign=self.foreign if kind=='clientes' else self.foreign_entity
            self.assertEqual(self.client.get('/recadclientes/api/opcoes/',{'tipo':kind,'id':foreign.pk}).data['count'],0)
        response=self.client.get('/recadclientes/api/opcoes/',{'tipo':'municipios','uf':self.uf.pk});self.assertEqual(response.data['count'],1)
        self.assertEqual(self.client.get(self.url(),{'search':'Alfa','page_size':1}).data['count'],1)
        self.assertEqual(self.client.get(self.url('usuarios'),{'entidade':self.entity.pk}).data['count'],1)
        self.assertEqual(self.client.get(self.url('usuarios'),{'entidade':self.foreign_entity.pk}).data['count'],0)
        self.assertEqual(self.client.get('/recadclientes/api/opcoes/',{'tipo':'bad'}).status_code,400)
        self.assertEqual(self.client.get(self.url(),{'cliente':'bad'}).status_code,400)

    def test_mass_assignment_cannot_change_privileges_or_create_nested_contacts(self):
        response=self.client.post(self.url(),self.values(empresa=self.other.pk,usuarios=[{'nome_completo':'Ignorado'}],is_superuser=True),format='json')
        self.assertEqual(response.status_code,201,response.data)
        entity=EntidadeRecad.objects.get(pk=response.data['id']);self.assertEqual(entity.cliente.empresa_id,self.company.pk)
        self.assertFalse(entity.usuarios.exists());self.user.refresh_from_db();self.assertFalse(self.user.is_superuser)

    def test_model_clean_validates_without_drf(self):
        with self.assertRaises(ValidationError):EntidadeRecad(cliente=self.customer,nome=' ',telefone='bad').clean()
        with self.assertRaises(ValidationError):UsuarioRecad(entidade=self.entity,nome_completo='',email='bad').clean()
        with self.assertRaises(ValidationError):EntidadeRecad(cliente=self.customer,nome='Teste',uf=self.uf,cidade=self.foreign_city).clean()

    @override_settings(SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
    def test_session_csrf(self):
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url(),self.values(),format='json',HTTP_X_EMPRESA_ID=str(self.company.pk)).status_code,403)
        token=client.get('/clientes/api/auth/csrf/').data['csrfToken']
        self.assertEqual(client.post(self.url(),self.values(),format='json',HTTP_X_EMPRESA_ID=str(self.company.pk),HTTP_X_CSRFTOKEN=token).status_code,201)

    def test_admin_read_only_and_scoped_for_all_models(self):
        request=RequestFactory().get('/admin/');request.user=self.user
        for model in MODELOS_RECAD:
            admin=site._registry[model]
            self.assertFalse(admin.has_add_permission(request));self.assertFalse(admin.has_change_permission(request));self.assertFalse(admin.has_delete_permission(request))
        self.assertEqual(site._registry[EntidadeRecad].get_queryset(request).count(),2)
