import json
import os
import tempfile
import uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone as dt_timezone
from unittest.mock import patch
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from auditlog.models import LogEntry
from empresa.models import Empresa
from usuario.models import Usuario
from clientes.models import Cliente
from contratos.models import Contrato
from notas.models import Nota,OperacaoFiscal
from notas.gateway import certificate_path
from .models import Ambiente
from .fields import PREFIX


def synthetic_certificate(password='test-password',expired=False):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Synthetic isolated certificate')])
    now=datetime.now(dt_timezone.utc)
    cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=10)).not_valid_after(now+timedelta(days=-1 if expired else 30)).sign(key,hashes.SHA256())
    return pkcs12.serialize_key_and_certificates(b'test',key,cert,None,serialization.BestAvailableEncryption(password.encode()) if password else serialization.NoEncryption())


class AmbienteAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company=Empresa.objects.create(cnpj='1',razao='Empresa Alfa');cls.other=Empresa.objects.create(cnpj='2',razao='Empresa Beta')
        cls.user=Usuario.objects.create_user(username='ambiente_test',email='ambiente@example.test',password='test');cls.user.empresas.add(cls.company)
        cls.user.user_permissions.set(Permission.objects.filter(content_type__app_label='configambiente'))
        cls.conf=Ambiente.objects.create(empresa=cls.company,descricao='Ambiente Alfa',certificado='missing.pfx',senha='old-test-password',homologacao=True,numero_lote='10',numero_rps='20',aliquota_iss=5)
        cls.foreign=Ambiente.objects.create(empresa=cls.other,descricao='Ambiente Beta',certificado='',senha='foreign-test-password')
        customer=Cliente.objects.create(empresa=cls.company,instituicao='Cliente Alfa')
        contract=Contrato.objects.create(empresa=cls.company,cliente=customer)
        cls.note=Nota.objects.create(empresa=cls.company,contrato=contract,dt_data_emissao=timezone.now(),competencia=1,exercicio=2026,numero_lote=11,numero_rps=21)
    def setUp(self):
        self.client=APIClient();self.client.force_authenticate(self.user);self.client.credentials(HTTP_X_EMPRESA_ID=str(self.company.pk))
        self.private=self.enterContext(tempfile.TemporaryDirectory());self.enterContext(self.settings(PRIVATE_CERTIFICATE_ROOT=self.private))
    def url(self,pk=None,action=''):return '/configambiente/api/ambientes/'+(str(pk)+'/' if pk else '')+action
    def upload(self,data=None,password='test-password'):
        return self.client.patch(self.url(self.conf.pk),{'certificado':SimpleUploadedFile('secret-name.pfx',data or synthetic_certificate(password),content_type='application/x-pkcs12'),'senha':password},format='multipart')
    def pending(self,state='executando'):
        return OperacaoFiscal.objects.create(nota=self.note,usuario=self.user,acao='emitir',chave=uuid.uuid4(),estado=state)
    def test_auth_company_and_no_secret_in_responses(self):
        response=self.client.get(self.url());self.assertEqual(response.status_code,200,response.data);self.assertEqual(response.data['count'],1)
        row=response.data['results'][0];self.assertNotIn('senha',row);self.assertNotIn('certificado',row);self.assertNotIn('old-test-password',json.dumps(row));self.assertNotIn('missing.pfx',json.dumps(row))
        self.assertEqual(self.client.get(self.url(self.foreign.pk)).status_code,404)
        self.assertEqual(self.client.patch(self.url(self.foreign.pk),{'descricao':'X'},format='json').status_code,404)
        self.client.force_authenticate(None);self.assertEqual(self.client.get(self.url()).status_code,401)
    def test_password_encrypted_at_rest_and_decrypted_only_for_application(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT senha FROM configambiente_ambiente WHERE id=%s',[self.conf.pk]);stored=cursor.fetchone()[0]
        self.assertTrue(stored.startswith(PREFIX));self.assertNotIn('old-test-password',stored)
        self.conf.refresh_from_db();self.assertEqual(self.conf.senha,'old-test-password')
    def test_private_certificate_upload_validation_permissions_and_gateway_compatibility(self):
        response=self.upload();self.assertEqual(response.status_code,200,response.data)
        self.conf.refresh_from_db();path=certificate_path(self.conf);self.assertIsNotNone(path);self.assertTrue(path.is_relative_to(Path(self.private)))
        self.assertEqual(os.stat(path).st_mode&0o777,0o600);self.assertNotIn('secret-name',str(path));self.assertEqual(self.conf.senha,'test-password')
        with self.assertRaises(ValueError):self.conf.certificado.url
        self.assertNotIn('senha',response.data);self.assertNotIn('certificado',response.data)
        logs=json.dumps(list(LogEntry.objects.filter(object_pk=str(self.conf.pk)).values('changes')),default=str)
        self.assertNotIn('test-password',logs);self.assertNotIn('secret-name',logs)
    def test_invalid_wrong_password_expired_and_large_files_do_not_replace(self):
        for data,password in [(b'bad','test-password'),(synthetic_certificate(),'wrong'),(synthetic_certificate(expired=True),'test-password'),(b'x'*(5*1024*1024+1),'test-password')]:
            response=self.upload(data,password);self.assertEqual(response.status_code,400,response.data)
        self.conf.refresh_from_db();self.assertEqual(self.conf.certificado.name,'missing.pfx');self.assertEqual(self.conf.senha,'old-test-password')
        self.assertEqual(list(Path(self.private).glob('*.pfx')),[])
    def test_omitted_or_empty_password_preserves_existing_credential(self):
        response=self.client.patch(self.url(self.conf.pk),{'descricao':'Editado','senha':''},format='json');self.assertEqual(response.status_code,200,response.data)
        self.conf.refresh_from_db();self.assertEqual(self.conf.senha,'old-test-password')
        self.assertEqual(self.client.patch(self.url(self.conf.pk),{'senha':'changed'},format='json').status_code,400)
    def test_production_requires_explicit_confirmation(self):
        response=self.client.patch(self.url(self.conf.pk),{'homologacao':False},format='json');self.assertEqual(response.status_code,400,response.data)
        response=self.client.patch(self.url(self.conf.pk),{'homologacao':False,'confirmar_producao':True},format='json');self.assertEqual(response.status_code,200,response.data)
        self.conf.refresh_from_db();self.assertFalse(self.conf.homologacao)
    def test_sequences_cannot_be_overwritten_or_reduced_and_require_permission(self):
        self.assertEqual(self.client.patch(self.url(self.conf.pk),{'numero_rps':'0'},format='json').status_code,400)
        values={'numero_lote':11,'numero_rps':21,'confirmar':True}
        response=self.client.post(self.url(self.conf.pk,'ajustar_sequencias/'),values,format='json');self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.client.post(self.url(self.conf.pk,'ajustar_sequencias/'),{**values,'numero_rps':20},format='json').status_code,400)
        self.assertEqual(self.client.post(self.url(self.conf.pk,'ajustar_sequencias/'),{**values,'confirmar':False},format='json').status_code,400)
        self.user.user_permissions.remove(Permission.objects.get(content_type__app_label='configambiente',codename='ajustar_sequencias_ambiente'));self.user=Usuario.objects.get(pk=self.user.pk);self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(self.url(self.conf.pk,'ajustar_sequencias/'),values,format='json').status_code,403)
    def test_pending_and_uncertain_operations_block_metadata_credentials_and_sequence(self):
        for state in ['executando','incerta']:
            op=self.pending(state)
            self.assertEqual(self.client.patch(self.url(self.conf.pk),{'descricao':'Bloqueado'},format='json').status_code,409)
            self.assertEqual(self.upload().status_code,409)
            self.assertEqual(self.client.post(self.url(self.conf.pk,'ajustar_sequencias/'),{'numero_lote':30,'numero_rps':30,'confirmar':True},format='json').status_code,409)
            op.delete()
        self.conf.refresh_from_db();self.assertEqual(self.conf.descricao,'Ambiente Alfa')
    def test_one_environment_per_company_and_history_initial_sequences(self):
        response=self.client.post(self.url(),{'descricao':'Duplicate'},format='json');self.assertEqual(response.status_code,400,response.data)
        self.conf.delete()
        response=self.client.post(self.url(),{'descricao':'Novo','aliquota_iss':'5.0000'},format='json');self.assertEqual(response.status_code,201,response.data)
        obj=Ambiente.objects.get(pk=response.data['id']);self.assertEqual(obj.empresa_id,self.company.pk);self.assertTrue(obj.homologacao);self.assertEqual(obj.numero_lote,'11');self.assertEqual(obj.numero_rps,'21')
    def test_invalid_percentages_and_metadata(self):
        for values in [{'aliquota_iss':'101'},{'aliquota_iss':'-1'},{'aliquota_iss':'NaN'},{'descricao':' '},{'coigo_servico':'123456'}]:
            self.assertEqual(self.client.patch(self.url(self.conf.pk),values,format='json').status_code,400)
    def test_reader_csrf_legacy_and_readiness_are_readonly(self):
        reader=Usuario.objects.create_user(username='ambiente_reader',email='reader@example.test',password='test');reader.empresas.add(self.company)
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='configambiente',codename='view_ambiente'));self.client.force_authenticate(reader)
        self.assertEqual(self.client.get(self.url()).status_code,200);self.assertEqual(self.client.patch(self.url(self.conf.pk),{'descricao':'X'},format='json').status_code,403)
        self.assertEqual(self.client.get(self.url(self.conf.pk,'prontidao/')).status_code,200)
        self.assertEqual(self.client.get('/configambiente/list/').url,'/clientes/app/ambiente-fiscal')
        client=APIClient(enforce_csrf_checks=True);client.force_login(self.user);self.assertEqual(client.patch(self.url(self.conf.pk),{'descricao':'X'},format='json').status_code,403)
    def test_failure_after_private_file_write_rolls_back_db_and_removes_only_new_file(self):
        with patch('configambiente.services.auditar',side_effect=RuntimeError('simulated failure')):
            with self.assertRaises(RuntimeError):self.upload()
        self.conf.refresh_from_db();self.assertEqual(self.conf.certificado.name,'missing.pfx');self.assertEqual(self.conf.senha,'old-test-password')
        self.assertEqual(list(Path(self.private).glob('*.pfx')),[])

    def test_password_can_be_read_with_previous_application_key_during_rotation(self):
        from django.conf import settings
        previous=settings.SECRET_KEY
        with self.settings(SECRET_KEY='rotated-test-key-only',SECRET_KEY_FALLBACKS=[previous]):
            self.conf.refresh_from_db()
            self.assertEqual(self.conf.senha,'old-test-password')
