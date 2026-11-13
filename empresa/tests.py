from io import BytesIO
from pathlib import Path
import tempfile
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from PIL import Image
from clientes.models import Uf,Municipio,Cliente
from usuario.models import Usuario
from .models import Empresa


def cnpj(base='123456780001'):
    digits=[int(d) for d in base]
    for weights in ([5,4,3,2,9,8,7,6,5,4,3,2],[6,5,4,3,2,9,8,7,6,5,4,3,2]):
        remainder=sum(d*w for d,w in zip(digits,weights))%11
        digits.append(0 if remainder<2 else 11-remainder)
    return ''.join(str(d) for d in digits)


class EmpresaAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.uf=Uf.objects.create(sigla='CE',descricao='Ceará');cls.other_uf=Uf.objects.create(sigla='PI',descricao='Piauí')
        cls.city=Municipio.objects.create(uf=cls.uf,descricao='Fortaleza',codigo_ibge='2304400')
        cls.company=Empresa.objects.create(cnpj=cnpj(),razao='Empresa Alfa',inscricao_municipal='000123',cidade=cls.city,uf=cls.uf)
        cls.other=Empresa.objects.create(cnpj=cnpj('234567890001'),razao='Empresa Beta',inscricao_municipal='000456',cidade=cls.city,uf=cls.uf)
        cls.user=Usuario.objects.create_user(username='empresa_test',email='empresa@example.test',password='test');cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='empresa'))
    def setUp(self):
        self.client=APIClient();self.client.force_authenticate(self.user)
        self.media=self.enterContext(tempfile.TemporaryDirectory());self.enterContext(self.settings(MEDIA_ROOT=self.media))
    def url(self,pk=None):return '/empresa/api/empresas/'+(str(pk)+'/' if pk else '')
    def values(self,**changes):return {'cnpj':cnpj('345678900001'),'razao':'Nova empresa','inscricao_municipal':'000789','cidade':self.city.pk,'uf':self.uf.pk,**changes}
    def image(self,name='logo.png'):
        data=BytesIO();Image.new('RGB',(8,8),'red').save(data,format='PNG');return SimpleUploadedFile(name,data.getvalue(),content_type='image/png')
    def test_membership_scope_foreign_ids_and_auth(self):
        self.assertEqual(self.client.get(self.url()).data['count'],1)
        for method in ['get','delete']:self.assertEqual(getattr(self.client,method)(self.url(self.other.pk)).status_code,404)
        self.assertEqual(self.client.patch(self.url(self.other.pk),{'razao':'Mudou'},format='json').status_code,404)
        self.client.force_authenticate(None);self.assertEqual(self.client.get(self.url()).status_code,401)
    def test_create_only_links_creator_and_updates_me(self):
        response=self.client.post(self.url(),self.values(),format='json');self.assertEqual(response.status_code,201,response.data)
        pk=response.data['id'];self.assertTrue(self.user.empresas.filter(pk=pk).exists())
        self.assertEqual(list(Usuario.objects.filter(empresas__pk=pk).values_list('pk',flat=True)),[self.user.pk])
        self.assertEqual(self.client.get(self.url()).data['count'],2)
    def test_invalid_cnpj_required_fields_city_uf_and_duplicate_normalization(self):
        original=self.company.cnpj
        formatted=original[:2]+'.'+original[2:5]+'.'+original[5:8]+'/'+original[8:12]+'-'+original[12:]
        for changes in [{'cnpj':'123'},{'cnpj':'00000000000000'},{'razao':' '},{'uf':self.other_uf.pk},{'cidade':None},{'cnpj':formatted}]:
            response=self.client.post(self.url(),self.values(**changes),format='json');self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(Empresa.objects.count(),2)
    def test_logo_validated_and_optional_preserved_and_removed_without_deleting_file(self):
        response=self.client.post(self.url(),{**self.values(),'logo':self.image('untrusted.png')},format='multipart');self.assertEqual(response.status_code,201,response.data)
        obj=Empresa.objects.get(pk=response.data['id']);name=obj.logo.name;path=Path(obj.logo.path)
        self.assertTrue(name.endswith('.png'));self.assertNotIn('untrusted',name);self.assertTrue(path.exists())
        response=self.client.patch(self.url(obj.pk),{'razao':'Editada'},format='json');self.assertEqual(response.status_code,200,response.data)
        obj.refresh_from_db();self.assertEqual(obj.logo.name,name)
        response=self.client.patch(self.url(obj.pk),{'remover_logo':True},format='json');self.assertEqual(response.status_code,200,response.data)
        obj.refresh_from_db();self.assertFalse(obj.logo);self.assertTrue(path.exists())
    def test_invalid_logo_rejected_without_creating_company(self):
        for file in [SimpleUploadedFile('logo.svg',b'<svg/>',content_type='image/svg+xml'),SimpleUploadedFile('bad.png',b'not-an-image',content_type='image/png')]:
            response=self.client.post(self.url(),{**self.values(),'logo':file},format='multipart');self.assertEqual(response.status_code,400,response.data)
        self.assertEqual(Empresa.objects.count(),2)
    def test_permission_actions_readonly_and_create_without_previous_membership(self):
        creator=Usuario.objects.create_user(username='empresa_creator',email='creator@example.test',password='test')
        creator.user_permissions.add(Permission.objects.get(content_type__app_label='empresa',codename='add_empresa'))
        self.client.force_authenticate(creator)
        self.assertEqual(self.client.get(self.url()).status_code,403)
        response=self.client.post(self.url(),self.values(),format='json');self.assertEqual(response.status_code,201,response.data)
        self.assertTrue(creator.empresas.filter(pk=response.data['id']).exists())
        self.assertEqual(self.client.patch(self.url(response.data['id']),{'razao':'Mudou'},format='json').status_code,403)
        self.assertEqual(self.client.delete(self.url(response.data['id'])).status_code,403)
    def test_select_company_checks_membership_and_preserves_session_on_failure(self):
        response=self.client.post('/empresa/api/selecionar/',{'empresa':self.company.pk},format='json');self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.session['empresa'],self.company.pk)
        response=self.client.post('/empresa/api/selecionar/',{'empresa':self.other.pk},format='json');self.assertEqual(response.status_code,403)
        self.assertEqual(self.client.session['empresa'],self.company.pk)
        self.assertEqual(self.client.post('/empresa/api/selecionar/',{'empresa':'bad'},format='json').status_code,400)
        self.assertEqual(self.client.get('/empresa/select_empresa/').status_code,405)
    def test_selection_does_not_require_company_admin_permission_and_legacy_payload(self):
        user=Usuario.objects.create_user(username='empresa_member',email='member@example.test',password='test');user.empresas.add(self.company)
        self.client.force_authenticate(user)
        response=self.client.post('/empresa/select_empresa/',{'empresa_select':self.company.pk},format='json');self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.session['empresa_nome'],'Empresa Alfa')
        self.assertEqual(self.client.get('/empresa/api/opcoes/?tipo=ufs').status_code,403)
    def test_protected_delete_keeps_company_and_membership(self):
        Cliente.objects.create(empresa=self.company,instituicao='Cliente vinculado')
        response=self.client.delete(self.url(self.company.pk));self.assertEqual(response.status_code,409,response.data)
        self.assertTrue(self.user.empresas.filter(pk=self.company.pk).exists())
    def test_delete_empty_company_refresh_membership_and_clear_active_session(self):
        response=self.client.post(self.url(),self.values(),format='json');pk=response.data['id']
        self.client.post('/empresa/api/selecionar/',{'empresa':pk},format='json')
        self.assertEqual(self.client.delete(self.url(pk)).status_code,204)
        self.assertFalse(self.user.empresas.filter(pk=pk).exists());self.assertNotIn('empresa',self.client.session)
    def test_session_csrf_and_legacy_redirect(self):
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url(),self.values(),format='json').status_code,403)
        self.assertEqual(client.post('/empresa/select_empresa/',{'empresa_select':self.company.pk}).status_code,403)
        self.assertEqual(self.client.get('/empresa/lista_empresa/').url,'/clientes/app/empresas')

    def test_existing_invalid_cnpj_is_readable_and_flagged_without_rewriting(self):
        self.company.cnpj='00000000000000';self.company.save()
        response=self.client.get(self.url(self.company.pk))
        self.assertEqual(response.status_code,200,response.data)
        self.assertFalse(response.data['cnpj_valido'])
        self.company.refresh_from_db();self.assertEqual(self.company.cnpj,'00000000000000')
