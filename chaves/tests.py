import hashlib
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from clientes.models import Cliente,Uf,Parceiro
from empresa.models import Empresa
from usuario.models import Usuario
from servicos.models import Servico
from .models import ChaveServico

@override_settings(API_SECRET_KEY='isolated-service-key-tests-only')
class ServiceKeyAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Empresa.objects.create(cnpj='1',razao='Empresa Alfa');cls.other=Empresa.objects.create(cnpj='2',razao='Empresa Beta')
        cls.uf=Uf.objects.create(sigla='CE',descricao='Ceará');cls.other_uf=Uf.objects.create(sigla='PI',descricao='Piauí')
        cls.customer=Cliente.objects.create(empresa=cls.company,instituicao='Cliente Alfa',cnpj='11222333000181',uf=cls.uf,ativo=True,desativar=False)
        cls.second=Cliente.objects.create(empresa=cls.company,instituicao='Outro cliente',cnpj='11222333000182',uf=cls.other_uf)
        cls.foreign_customer=Cliente.objects.create(empresa=cls.other,instituicao='Cliente Beta',cnpj='11222333000183',uf=cls.uf)
        cls.service=Servico.objects.create(empresa=cls.company,cliente=cls.customer,descricao='Servico ALFA')
        cls.second_service=Servico.objects.create(empresa=cls.company,cliente=cls.second,descricao='Servico PI')
        cls.foreign_service=Servico.objects.create(empresa=cls.other,cliente=cls.foreign_customer,descricao='Servico BETA')
        cls.user=Usuario.objects.create_user(username='chaves_test',email='chaves@example.test',password='test');cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='chaves'))
        cls.foreign_key=ChaveServico.objects.create(cliente=cls.foreign_customer,servico=cls.foreign_service,competencia='01',exercicio=2026,dt_liberacao=timezone.now(),chave='foreign-test-only')
    def setUp(self):
        self.client=APIClient();self.client.force_authenticate(self.user);self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))
    def url(self,pk=None,action=''):return '/chave/api/chaves/'+(str(pk)+'/' if pk else '')+action
    def values(self,**changes):return {'cliente':self.customer.pk,'servico':self.service.pk,'competencia':'1','exercicio':2026,**changes}
    def create_key(self,**changes):
        response=self.client.post(self.url(),self.values(**changes),format='json');self.assertEqual(response.status_code,201,response.data);return ChaveServico.objects.get(pk=response.data['id'])
    def test_legacy_hash_normalization_server_fields_and_timezone(self):
        obj=self.create_key(chave='injected',usuario=999,dt_liberacao='2000-01-01')
        payload=self.service.descricao+self.customer.cnpj+'01'+'2026'+settings.API_SECRET_KEY
        self.assertEqual(obj.chave,hashlib.md5(payload.encode('ascii')).hexdigest());self.assertEqual(obj.competencia,'01');self.assertEqual(obj.usuario_id,self.user.pk);self.assertTrue(timezone.is_aware(obj.dt_liberacao))
    def test_company_scope_foreign_ids_and_missing_regeneration(self):
        for method in ['get','delete']:
            self.assertEqual(getattr(self.client,method)(self.url(self.foreign_key.pk)).status_code,404)
        self.assertEqual(self.client.post(self.url(self.foreign_key.pk,'atualizar/')).status_code,404)
        self.assertEqual(self.client.post(self.url(999999,'atualizar/')).status_code,404)
        self.assertEqual(self.client.patch(self.url(self.foreign_key.pk),self.values(),format='json').status_code,404)
        self.client.credentials(HTTP_X_EMPRESA_ID=str(self.other.pk));self.assertEqual(self.client.get(self.url()).status_code,403)
    def test_bad_month_year_customer_service_and_unicode_do_not_create_keys(self):
        for changes in [{'competencia':'13'},{'competencia':'0'},{'competencia':'a'},{'competencia':'١'},{'exercicio':1899},{'exercicio':10000},{'servico':self.foreign_service.pk},{'servico':self.second_service.pk},{'servico':None}]:
            response=self.client.post(self.url(),self.values(**changes),format='json');self.assertEqual(response.status_code,400,response.data)
        self.service.descricao='Serviço acentuado';self.service.save()
        self.assertEqual(self.client.post(self.url(),self.values(),format='json').status_code,400)
        self.assertEqual(ChaveServico.objects.count(),1)
    def test_duplicate_business_key_edit_and_delete(self):
        obj=self.create_key()
        self.assertEqual(self.client.post(self.url(),self.values(competencia='01'),format='json').status_code,409)
        response=self.client.patch(self.url(obj.pk),{'competencia':'2'},format='json');self.assertEqual(response.status_code,200,response.data)
        obj.refresh_from_db();self.assertEqual(obj.competencia,'02')
        self.assertEqual(self.client.delete(self.url(obj.pk)).status_code,204)
    def test_regeneration_uses_current_customer_data(self):
        obj=self.create_key();old=obj.chave;self.customer.cnpj='11222333000199';self.customer.save()
        response=self.client.post(self.url(obj.pk,'atualizar/'));self.assertEqual(response.status_code,200,response.data)
        obj.refresh_from_db();self.assertNotEqual(obj.chave,old)
        self.assertEqual(self.client.post(self.url(obj.pk,'atualizar/')).data['chave'],obj.chave)
    def test_missing_cnpj_and_historical_inconsistent_rows_are_preserved(self):
        self.customer.cnpj='';self.customer.save()
        self.assertEqual(self.client.post(self.url(),self.values(),format='json').status_code,400)
        missing=ChaveServico.objects.create(cliente=self.customer,servico=None,competencia='01',exercicio=2026,chave='orphan-test-only',dt_liberacao=timezone.now())
        mismatch=ChaveServico.objects.create(cliente=self.customer,servico=self.second_service,competencia='01',exercicio=2026,chave='mismatch-test-only',dt_liberacao=timezone.now())
        self.assertEqual(self.client.get(self.url()).data['count'],0)
        self.assertEqual(self.client.get(self.url(missing.pk)).status_code,404)
        self.assertTrue(ChaveServico.objects.filter(pk=mismatch.pk).exists())
    def test_readonly_legacy_permission_cannot_recalculate_or_write(self):
        obj=self.create_key();reader=Usuario.objects.create_user(username='chaves_reader',email='reader@example.test',password='test');reader.empresas.add(self.company)
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='chaves',codename='view_chaves'))
        self.client.force_authenticate(reader)
        self.assertEqual(self.client.get(self.url()).status_code,200)
        self.assertEqual(self.client.get('/chave/api/opcoes/').status_code,200)
        self.assertEqual(self.client.post(self.url(obj.pk,'atualizar/')).status_code,403)
        self.assertEqual(self.client.patch(self.url(obj.pk),{'competencia':'2'},format='json').status_code,403)
        self.assertEqual(self.client.delete(self.url(obj.pk)).status_code,403)
        self.assertEqual(self.client.post(self.url(),self.values(),format='json').status_code,403)
    def test_uf_scope_and_service_options_filter(self):
        self.user.uf=self.uf;self.user.save()
        self.assertEqual(self.client.get('/chave/api/opcoes/?tipo=clientes').data['count'],1)
        response=self.client.get('/chave/api/opcoes/',{'tipo':'servicos','cliente':self.customer.pk});self.assertEqual(response.data['count'],1)
        response=self.client.post(self.url(),self.values(cliente=self.second.pk,servico=self.second_service.pk),format='json');self.assertEqual(response.status_code,400)
    def test_session_csrf_legacy_http_and_filters(self):
        obj=self.create_key();client=APIClient(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(self.url(),self.values(),format='json').status_code,403)
        self.assertEqual(self.client.get('/chave/list/').url,'/clientes/app/chaves')
        self.assertEqual(self.client.get(f'/chave/update_chave/{obj.pk}/').status_code,405)
        response=self.client.get(self.url(),{'cliente':self.customer.pk,'competencia':1,'exercicio':2026});self.assertEqual(response.data['count'],1)
        self.assertEqual(self.client.get(self.url(),{'competencia':13}).status_code,400)
    def test_default_year_is_current_and_not_2018(self):
        self.assertEqual(ChaveServico().exercicio,timezone.localdate().year)
    def test_existing_external_consumer_can_find_new_key(self):
        partner=Parceiro.objects.create(empresa=self.company,instituicao='Parceiro teste',excecao=False)
        self.customer.parceiro=partner;self.customer.save();obj=self.create_key()
        payload=self.service.descricao+self.customer.cnpj+'012026'+settings.API_SECRET_KEY
        with patch('api.views.settings.API_SECRET_KEY',settings.API_SECRET_KEY):
            response=self.client.post('/api/libera_servicos/',{'servico':self.service.descricao,'cnpj':self.customer.cnpj,'competencia':'012026','key':hashlib.md5(payload.encode('ascii')).hexdigest()})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['liberado']);self.assertEqual(response.json()['usuario'],self.user.username)
