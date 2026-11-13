import hashlib
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from clientes.models import Cliente, Liberacao, LiberacaoDatas, Parceiro, Uf, Municipio
from contratos.models import Contrato
from empresa.models import Empresa
from financeiro.models import Configuracao, DocReceita
from notas.models import Nota
from servicos.models import Servico
from chaves.models import ChaveServico
from usuario.models import Usuario

TODAY = date(2026, 11, 5)
SECRET = 'isolated-integration-tests-only'


@override_settings(API_SECRET_KEY=SECRET, PUBLIC_APP_URL='https://example.test')
class IntegracaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Empresa.objects.create(cnpj='1',razao='Empresa teste')
        cls.other=Empresa.objects.create(cnpj='2',razao='Outra empresa')
        cls.actor=Usuario.objects.create_user(username='integration',email='integration@example.test',password='test')
        cls.partner=Parceiro.objects.create(empresa=cls.company,instituicao='Parceiro teste',excecao=False)
        cls.customer=Cliente.objects.create(empresa=cls.company,instituicao='Cliente teste',codigoentidade='0001',codigolayout='0002',cnpj='11.222.333/0001-81')
        cls.contract=Contrato.objects.create(empresa=cls.company,cliente=cls.customer,ativo=True)
        cls.note=Nota.objects.create(empresa=cls.company,contrato=cls.contract,numero='TESTE',dt_data_emissao=timezone.now(),competencia=11,exercicio=2026,valor_liquido=Decimal('100.00'))
        cls.config=Configuracao.objects.create(pk=1,descricao='Teste',liberaquantnotasabertas=1)
    def setUp(self):
        cache.clear();self.client=Client(enforce_csrf_checks=True)
        self.enterContext(self.settings(API_INTEGRATION_USER_ID=self.actor.pk))
        self.enterContext(patch('api.services.timezone.localdate',return_value=TODAY))
    def payload(self,kind='delphi',**changes):
        if kind=='servico':data={'servico':'SERVICO TESTE','cnpj':self.customer.cnpj,'competencia':'112026'}
        elif kind=='transparencia':data={'codigo':'0001','codigo_layout':'0002','tipo':'1'}
        else:data={'codigo':'0001','codigo_layout':'0002','competencia':'112026'}
        if kind=='web':data.update(codigo='0002',codigo_layout='0001')
        data.update(changes)
        if kind=='servico':raw=data['servico']+data['cnpj']+data['competencia']+SECRET
        else:raw=data['codigo_layout']+data['codigo']+(data['tipo'] if kind=='transparencia' else data['competencia'])+SECRET
        if kind=='web':raw+=TODAY.strftime('%d%m%Y')
        data['key']=(hashlib.sha256 if kind=='web' else hashlib.md5)(raw.encode('ascii')).hexdigest()
        return data
    def post(self,route='libera_delphi',kind='delphi',**changes):return self.client.post('/api/'+route+'/',self.payload(kind,**changes))
    def grant(self):
        record=Liberacao(cliente=self.customer,competencia='11',exercicio=2026,usuario=self.actor,dt_liberacao=timezone.now())
        record.atualizar_chave();record.save();return record
    def service(self):
        self.customer.parceiro=self.partner;self.customer.save()
        service=Servico.objects.create(cliente=self.customer,empresa=self.company,descricao='SERVICO TESTE')
        return ChaveServico.objects.create(cliente=self.customer,servico=service,competencia='11',exercicio=2026,chave='synthetic-key',usuario=self.actor,dt_liberacao=timezone.now())
    def test_new_and_existing_release_keep_distinct_legacy_response_signatures(self):
        response=self.post();self.assertEqual(response.status_code,200,response.content);data=response.json()
        self.assertTrue(data['liberado']);self.assertEqual(data['usuario'],self.actor.username)
        self.assertEqual(data['data_liberacao'],TODAY.isoformat())
        self.assertEqual(data['key'],hashlib.md5(('00010002112026sucesso'+SECRET+'05112026').encode()).hexdigest())
        record=Liberacao.objects.get(cliente=self.customer)
        self.assertEqual(record.chave,hashlib.md5(('00020001112026sucesso'+SECRET).encode()).hexdigest())
        again=self.post().json();self.assertTrue(again['liberado']);self.assertEqual(Liberacao.objects.count(),1)
        self.assertEqual(again['key'],hashlib.md5(('00010002112026sucesso'+SECRET).encode()).hexdigest())
    def test_bad_signature_and_missing_fields_do_not_query_database(self):
        with self.assertNumQueries(0):
            response=self.client.post('/api/libera_delphi/',{**self.payload(),'key':'0'*32})
        self.assertEqual(response.json(),{'error':'Parametros de requisição incorretos'})
        with self.assertNumQueries(0):response=self.client.post('/api/libera_delphi/',{'codigo':'0001'})
        self.assertIn('error',response.json());self.assertEqual(Liberacao.objects.count(),0)
    def test_malformed_and_non_ascii_inputs_fail_without_500(self):
        for changes in [{'competencia':'132026'},{'competencia':'1120000'},{'competencia':'110000'},{'codigo':'\u00e1'},{'codigo':"x' OR 1=1 --"},{'key':['a','b']}]:
            data={**self.payload(),**changes};response=self.client.post('/api/libera_delphi/',data)
            self.assertEqual(response.status_code,200,response.content);self.assertIn('error',response.json())
        self.assertFalse(Liberacao.objects.exists())
    def test_uppercase_md5_json_and_irrelevant_jwt_are_supported(self):
        data=self.payload();data['key']=data['key'].upper()
        response=self.client.post('/api/libera_delphi/',data,content_type='application/json',HTTP_AUTHORIZATION='Bearer irrelevant',HTTP_X_EMPRESA_ID=str(self.other.pk))
        self.assertTrue(response.json()['liberado']);self.assertEqual(Liberacao.objects.get().cliente_id,self.customer.pk)
    def test_unknown_inactive_disabled_and_ambiguous_clients_are_denied(self):
        self.assertFalse(self.post(codigo='9999').json()['liberado'])
        for attr in ['ativo','desativar','gerar_notas']:
            old=getattr(self.customer,attr);setattr(self.customer,attr,attr=='desativar');self.customer.save()
            self.assertFalse(self.post().json()['liberado']);setattr(self.customer,attr,old);self.customer.save()
        Cliente.objects.create(empresa=self.other,instituicao='Duplicado',codigoentidade='0001',codigolayout='0002')
        self.assertFalse(self.post().json()['liberado']);self.assertFalse(Liberacao.objects.exists())
    def test_threshold_denial_projects_only_legacy_invoice_fields(self):
        self.config.liberaquantnotasabertas=0;self.config.save()
        data=self.post().json();self.assertFalse(data['liberado'])
        self.assertEqual(set(data['notas'][0]),{'numero','vencimento','valor','competencia','url'})
        self.assertEqual(data['notas'][0]['valor'],'100.00');self.assertEqual(data['notas'][0]['competencia'],'Novembro')
        self.assertEqual(data['notas'][0]['url'],f'https://example.test/notas/montanota/{self.note.pk}/')
    def test_existing_manual_release_still_overrides_note_threshold_with_dated_response(self):
        self.grant();self.config.liberaquantnotasabertas=0;self.config.save()
        data=self.post().json();self.assertTrue(data['liberado'])
        self.assertEqual(data['key'],hashlib.md5(('00010002112026sucesso'+SECRET+'05112026').encode()).hexdigest())
    def test_partner_exception_keeps_legacy_meaning(self):
        self.customer.parceiro=self.partner;self.customer.save();self.config.liberaquantnotasabertas=0;self.config.save()
        self.assertTrue(self.post().json()['liberado'])
    def test_foreign_company_notes_do_not_affect_the_customer(self):
        self.note.empresa=self.other;self.note.save();self.assertFalse(self.post().json()['liberado'])
        self.assertFalse(Liberacao.objects.exists())
    def test_paid_document_uses_existing_situation_rule(self):
        self.config.liberaquantnotasabertas=0;self.config.save()
        DocReceita.objects.create(empresa=self.company,cliente=self.customer,nota=self.note,numero='REC',descricao='Teste',dt_vencimento=TODAY,valor=100,situacao='R',dt_registro=TODAY,user_registro=self.actor)
        self.assertTrue(self.post().json()['liberado'])
    def test_configuration_actor_and_database_failures_are_closed_and_rolled_back(self):
        Configuracao.objects.all().delete();self.assertEqual(self.post().status_code,503);self.assertFalse(Liberacao.objects.exists())
        Configuracao.objects.create(pk=1,descricao='Teste',liberaquantnotasabertas=1)
        with self.settings(API_INTEGRATION_USER_ID=999999):self.assertEqual(self.post().status_code,503)
        self.assertFalse(Liberacao.objects.exists())
        original=Liberacao.save
        def fail_after_save(obj,*args,**kwargs):original(obj,*args,**kwargs);raise DatabaseError('synthetic failure')
        with patch.object(Liberacao,'save',fail_after_save):self.assertEqual(self.post().status_code,503)
        self.assertFalse(Liberacao.objects.exists())
    def test_release_of_another_customer_is_never_reused(self):
        other=Cliente.objects.create(empresa=self.other,instituicao='Outra',codigoentidade='9999',codigolayout='9999')
        Liberacao.objects.create(cliente=other,codigo='0001',codigo_layout='0002',competencia='11',exercicio=2026,chave='synthetic-foreign',usuario=self.actor,dt_liberacao=timezone.now())
        self.config.liberaquantnotasabertas=0;self.config.save();self.assertFalse(self.post().json()['liberado'])
    def test_service_signature_and_output_match_original_consumer(self):
        record=self.service();response=self.post('libera_servicos','servico')
        self.assertEqual(response.status_code,200,response.content);data=response.json();self.assertTrue(data['liberado'])
        self.assertEqual(data['usuario'],record.usuario.username)
        self.assertEqual(data['key'],hashlib.md5(('SERVICO TESTE'+self.customer.cnpj+'112026sucesso'+SECRET).encode()).hexdigest())
    def test_service_unknown_missing_partner_and_corrupt_relations_deny(self):
        self.assertFalse(self.post('libera_servicos','servico').json()['liberado'])
        record=self.service();record.servico.empresa=self.other;record.servico.save()
        self.assertFalse(self.post('libera_servicos','servico').json()['liberado'])
        self.assertFalse(self.post('libera_servicos','servico',cnpj='unknown').json()['liberado'])
    def test_duplicate_service_identity_does_not_choose_arbitrary_key(self):
        first=self.service()
        ChaveServico.objects.create(cliente=self.customer,servico=first.servico,competencia='11',exercicio=2026,chave='second-key',usuario=self.actor,dt_liberacao=timezone.now())
        self.assertFalse(self.post('libera_servicos','servico').json()['liberado'])
    def test_block_period_is_parameterized_and_overlaps_take_restrictive_flags(self):
        LiberacaoDatas.objects.create(cliente=self.customer,dt_ate=TODAY.replace(day=1),dt_aparte=TODAY,libera_sistema=True,libera_tcm=True,libera_pagonline=True)
        LiberacaoDatas.objects.create(cliente=self.customer,dt_ate=TODAY.replace(day=1),dt_aparte=TODAY,libera_sistema=False,libera_tcm=True,libera_pagonline=False)
        self.assertEqual(self.post('bloqueia').json(),{'liberabloqueio':False,'liberatcm':True,'liberapagonline':False})
    def test_year_only_block_is_december_and_signature_uses_raw_year(self):
        LiberacaoDatas.objects.create(cliente=self.customer,dt_ate=date(2026,12,1),dt_aparte=date(2026,12,31),libera_sistema=False,libera_tcm=False,libera_pagonline=False)
        self.assertFalse(self.post('bloqueia',competencia='2026').json()['liberabloqueio'])
        self.assertTrue(self.post('bloqueia',competencia='112026').json()['liberabloqueio'])
    def test_unknown_block_customer_denies_all_flags(self):
        data=self.post('bloqueia',codigo='unknown').json()
        self.assertEqual([data[k] for k in ('liberabloqueio','liberatcm','liberapagonline')],[False]*3)
    def test_transparency_flags_and_current_month_blocks_take_precedence(self):
        self.assertTrue(self.post('libera_transparencia','transparencia').json()['liberado'])
        self.customer.libera_transparencia=False;self.customer.save()
        self.assertFalse(self.post('libera_transparencia','transparencia').json()['liberado'])
        self.assertTrue(self.post('libera_transparencia','transparencia',tipo='2').json()['liberado'])
        LiberacaoDatas.objects.create(cliente=self.customer,dt_ate=date(2026,11,1),dt_aparte=date(2026,11,30),gerar_notas=True,libera_contracheque=False)
        self.assertFalse(self.post('libera_transparencia','transparencia',tipo='2').json()['liberado'])
    def test_web_sha256_daily_signature_keeps_historical_lookup_order(self):
        self.assertTrue(self.post('libera','web').json()['liberado'])
        self.config.liberaquantnotasabertas=0;self.config.save();data=self.post('libera','web').json()
        self.assertFalse(data['liberado']);self.assertEqual(len(data['notas']),1)
        self.assertFalse(Liberacao.objects.exists())
    def test_public_entity_lookup_is_minimal_and_requires_ibge_code(self):
        uf=Uf.objects.create(sigla='CE',descricao='Ceará');city=Municipio.objects.create(uf=uf,descricao='Fortaleza',codigo_ibge='2304400')
        self.customer.cidade=city;self.customer.save()
        data=self.client.post('/api/cod_entidade/',{'municipio':'2304400'}).json()
        self.assertEqual(data,[{'cnpj':self.customer.cnpj,'instituicao':self.customer.instituicao,'codigoentidade':'0001'}])
        for invalid in ['',"x' OR 1=1 --",'123']:
            with self.assertNumQueries(0):self.assertEqual(self.client.post('/api/cod_entidade/',{'municipio':invalid}).json(),[])
    def test_recad_ack_does_not_print_or_persist_personal_data(self):
        with patch('sys.stdout',new_callable=StringIO) as output:
            data=self.post('recad_delphi',dados='synthetic-personal-contact').json()
        self.assertEqual(data,{});self.assertEqual(output.getvalue(),'');self.assertFalse(Liberacao.objects.exists())
    def test_http_methods_cache_headers_and_ip_throttle(self):
        response=self.client.get('/api/libera_delphi/');self.assertEqual(response.status_code,405);self.assertEqual(response['Cache-Control'],'no-store')
        cache.clear()
        with patch('api.views.LegacyIPThrottle.rate','1/min'):
            self.assertEqual(self.client.post('/api/libera_delphi/',{}).status_code,200)
            self.assertEqual(self.client.post('/api/libera_delphi/',{}).status_code,429)


@override_settings(API_SECRET_KEY=SECRET)
class IntegracaoConcorrenciaTests(TransactionTestCase):
    def test_two_simultaneous_requests_create_only_one_release(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections, connections
        from threading import Barrier
        cache.clear()
        company=Empresa.objects.create(cnpj='1',razao='Empresa concorrência')
        actor=Usuario.objects.create_user(username='concurrent',email='concurrent@example.test',password='test')
        partner=Parceiro.objects.create(empresa=company,instituicao='Parceiro concorrência',excecao=False)
        customer=Cliente.objects.create(empresa=company,instituicao='Cliente concorrência',codigoentidade='0001',codigolayout='0002',parceiro=partner)
        Configuracao.objects.create(pk=1,descricao='Teste',liberaquantnotasabertas=1)
        data={'codigo':'0001','codigo_layout':'0002','competencia':'112026','key':hashlib.md5(('00020001112026'+SECRET).encode()).hexdigest()}
        barrier=Barrier(2)
        def call():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                response=Client(enforce_csrf_checks=True).post('/api/libera_delphi/',data)
                return response.status_code,response.json()
            finally:connections.close_all()
        with self.settings(API_INTEGRATION_USER_ID=actor.pk),patch('api.services.timezone.localdate',return_value=TODAY),ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:call(),range(2)))
        for status,data in results:self.assertEqual(status,200);self.assertTrue(data['liberado'])
        self.assertEqual(Liberacao.objects.filter(cliente=customer).count(),1)
