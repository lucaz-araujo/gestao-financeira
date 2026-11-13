from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient
from empresa.models import Empresa
from usuario.models import Usuario
from conta.services import ContaConflict
from .models import Fornecedor,Unidade,Itens,Solicitacao,SolicitacaoItem,Orcamento,OrcamentoItens

class PurchaseAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Empresa.objects.create(cnpj='1',razao='Empresa Alfa');cls.other=Empresa.objects.create(cnpj='2',razao='Empresa Beta')
        cls.user=Usuario.objects.create_user(username='compras_test',email='compras@example.test',password='test');cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='compras'))
        cls.unit=Unidade.objects.create(empresa=cls.company,descricao='Unidade',sigla='UN')
        cls.item=Itens.objects.create(empresa=cls.company,descricao='Papel',unidade=cls.unit)
        cls.foreign_unit=Unidade.objects.create(empresa=cls.other,descricao='Outra',sigla='OUT')
        cls.foreign_item=Itens.objects.create(empresa=cls.other,descricao='Outro item',unidade=cls.foreign_unit)
        cls.supplier=Fornecedor.objects.create(empresa=cls.company,instituicao='Fornecedor Alfa')
        cls.foreign_supplier=Fornecedor.objects.create(empresa=cls.other,instituicao='Fornecedor Beta')
    def setUp(self):
        self.client=APIClient();self.client.force_authenticate(self.user);self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))
    def url(self,resource='solicitacoes',pk=None,action=''):return '/compras/api/'+resource+'/'+(str(pk)+'/' if pk else '')+action
    def post(self,resource,data,pk=None,action=''):return self.client.post(self.url(resource,pk,action),data,format='json')
    def request_data(self,**changes):return {'descricao':'Compra teste','dt_solicitacao':'2026-11-04','linhas':[{'item':self.item.pk,'quantidade':'2.500','valor':'10.125'}],**changes}
    def create_request(self,**changes):
        response=self.post('solicitacoes',self.request_data(**changes));self.assertEqual(response.status_code,201,response.data);return Solicitacao.objects.get(pk=response.data['id'])
    def quote_data(self,request,**changes):return {'solicitacao':request.pk,'fornecedor':self.supplier.pk,'dt_orcamento':'2026-11-04','linhas':[{'item':self.item.pk,'quantidade':'2.500','valor':'5.000'}],**changes}
    def create_quote(self,request,**changes):
        response=self.post('orcamentos',self.quote_data(request,**changes));self.assertEqual(response.status_code,201,response.data);return Orcamento.objects.get(pk=response.data['id'])
    def test_auth_permissions_company_csrf(self):
        self.client.force_authenticate(None);self.assertEqual(self.client.get(self.url()).status_code,401)
        self.client.force_authenticate(self.user);self.client.credentials(HTTP_X_EMPRESA_ID=str(self.other.pk));self.assertEqual(self.client.get(self.url()).status_code,403)
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.user);self.assertEqual(client.post(self.url(),{},format='json').status_code,403)
    def test_request_nested_server_totals_actor_and_readonly_fields(self):
        obj=self.create_request(status='FI',total='999',user_solicitante=999,empresa=self.other.pk)
        self.assertEqual(obj.status,'AB');self.assertEqual(obj.user_solicitante_id,self.user.pk);self.assertEqual(obj.empresa_id,self.company.pk)
        self.assertEqual(obj.total,Decimal('25.313'))
        self.assertEqual(obj.solicitacaoitem_set.get().valor_total,Decimal('25.313'))
    def test_nested_invalid_duplicate_foreign_and_overflow_roll_back(self):
        for lines in [[],[{'item':self.foreign_item.pk,'quantidade':'1','valor':'1'}],[{'item':self.item.pk,'quantidade':'0','valor':'1'}],[{'item':self.item.pk,'quantidade':'1','valor':'-1'}],[{'item':self.item.pk,'quantidade':'9999999','valor':'9999999'}],[{'item':self.item.pk,'quantidade':'1','valor':'1'}]*2]:
            response=self.post('solicitacoes',self.request_data(linhas=lines));self.assertEqual(response.status_code,400,response.data)
        self.assertFalse(Solicitacao.objects.exists());self.assertFalse(SolicitacaoItem.objects.exists())
    def test_request_update_delete_and_quote_lock(self):
        obj=self.create_request();response=self.client.patch(self.url(pk=obj.pk),{'linhas':[{'item':self.item.pk,'quantidade':'2.500','valor':'20'}]},format='json');self.assertEqual(response.status_code,200,response.data)
        obj.refresh_from_db();self.assertEqual(obj.total,Decimal('50'))
        self.create_quote(obj)
        self.assertEqual(self.client.patch(self.url(pk=obj.pk),{'descricao':'Alterou'},format='json').status_code,409)
        self.assertEqual(self.client.delete(self.url(pk=obj.pk)).status_code,409)
    def test_quote_must_match_request_quantity_and_company_atomic(self):
        obj=self.create_request()
        for values in [self.quote_data(obj,fornecedor=self.foreign_supplier.pk),self.quote_data(obj,linhas=[{'item':self.item.pk,'quantidade':'1','valor':'5'}])]:
            response=self.post('orcamentos',values);self.assertEqual(response.status_code,400,response.data)
        self.assertFalse(Orcamento.objects.exists());obj.refresh_from_db();self.assertEqual(obj.status,'AB')
    def test_quote_failure_after_parent_save_rolls_back(self):
        obj=self.create_request()
        with patch.object(OrcamentoItens,'save',side_effect=ContaConflict('Falha simulada')):
            self.assertEqual(self.post('orcamentos',self.quote_data(obj)).status_code,409)
        self.assertFalse(Orcamento.objects.exists());obj.refresh_from_db();self.assertEqual(obj.status,'AB')
    def test_finalization_scopes_lowest_price_to_request_and_updates_fk(self):
        obj=self.create_request();q1=self.create_quote(obj);q2=self.create_quote(obj,linhas=[{'item':self.item.pk,'quantidade':'2.500','valor':'4.111'}])
        unrelated=self.create_request();cheap=self.create_quote(unrelated,linhas=[{'item':self.item.pk,'quantidade':'2.500','valor':'0.001'}])
        response=self.post('solicitacoes',{'status':'AU'},obj.pk,'estado/');self.assertEqual(response.status_code,200,response.data)
        response=self.post('solicitacoes',{},obj.pk,'finalizar/');self.assertEqual(response.status_code,200,response.data)
        obj.refresh_from_db();row=obj.solicitacaoitem_set.get();self.assertEqual(obj.status,'FI');self.assertEqual(row.orcamento_id,q2.orcamentoitens.get().pk);self.assertEqual(obj.total,Decimal('10.278'))
        self.assertFalse(cheap.orcamentoitens.get().menor_preco);self.assertFalse(q1.orcamentoitens.get().menor_preco)
        self.assertEqual(self.post('solicitacoes',{},obj.pk,'finalizar/').status_code,200)
        self.assertEqual(self.client.patch(self.url('orcamentos',q2.pk),{'nr_documento':'Mudou'},format='json').status_code,409)
    def test_missing_quotes_and_invalid_transition(self):
        obj=self.create_request()
        self.assertEqual(self.post('solicitacoes',{},obj.pk,'finalizar/').status_code,409)
        self.assertEqual(self.post('solicitacoes',{'status':'PE'},obj.pk,'estado/').status_code,200)
        self.assertEqual(self.post('solicitacoes',{'status':'AU'},obj.pk,'estado/').status_code,409)
        self.assertEqual(self.post('solicitacoes',{'status':'FI'},obj.pk,'estado/').status_code,400)
    def test_approval_permission_and_owner_scope(self):
        owner=Usuario.objects.create_user(username='compras_owner',email='owner@example.test',password='test');owner.empresas.add(self.company)
        owner.user_permissions.set(Permission.objects.filter(content_type__app_label='compras').exclude(codename__in=['autorizar_solicitacao','finalizar_solicitacao']))
        hidden=self.create_request();self.client.force_authenticate(owner)
        self.assertEqual(self.client.get(self.url(pk=hidden.pk)).status_code,404)
        obj=self.create_request();self.create_quote(obj)
        self.assertEqual(self.post('solicitacoes',{'status':'AU'},obj.pk,'estado/').status_code,403)
        self.assertEqual(self.post('solicitacoes',{},obj.pk,'finalizar/').status_code,403)
    def test_cancel_and_legacy_redirect_no_mutation(self):
        obj=self.create_request();response=self.post('solicitacoes',{'status':'CA'},obj.pk,'estado/');self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.patch(self.url(pk=obj.pk),{'descricao':'X'},format='json').status_code,409)
        self.assertEqual(self.client.post('/compras/finalizar_solicitacao/',{'id':obj.pk}).status_code,302)
        self.assertEqual(self.client.get('/compras/list_forn/').url,'/clientes/app/compras-fornecedores')
    def test_catalog_company_uniqueness_and_protected_delete(self):
        response=self.post('itens',{'descricao':'Foreign','unidade':self.foreign_unit.pk});self.assertEqual(response.status_code,400)
        self.assertEqual(self.post('unidades',{'descricao':'Unidade','sigla':'UN'}).status_code,400)
        self.assertEqual(self.client.delete(self.url('unidades',self.unit.pk)).status_code,409)
        self.assertEqual(self.client.get(self.url('opcoes')+'?tipo=itens').data['count'],1)
        self.assertEqual(self.client.get(self.url('fornecedores',self.foreign_supplier.pk)).status_code,404)
    def test_supplier_documents_and_banking_zeros(self):
        values={'instituicao':'Novo fornecedor','endereco':'Rua','numero':'1','bairro':'Centro','cep':'60000000','agencia':'0001','conta':'0000123','dvconta':'X'}
        for invalid in [{'cnpj':'123'},{'cpf':'123'},{'resp_cpf':'123'},{'resp_email':'bad'}]:self.assertEqual(self.post('fornecedores',{**values,**invalid}).status_code,400)
        response=self.post('fornecedores',values);self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['agencia'],'0001');self.assertEqual(response.data['conta'],'0000123')
