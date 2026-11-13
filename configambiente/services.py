from datetime import datetime,timezone as dt_timezone
from django.db.models import Max
from rest_framework.exceptions import ValidationError
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from conta.services import ContaConflict
from notas.models import Nota,OperacaoFiscal
from notas.gateway import certificate_path
from .models import Ambiente


def periodo_seguro(empresa):
    if OperacaoFiscal.objects.filter(nota__empresa_id=empresa,acao__in=['emitir','cancelar','consultar','consultar_lote'],estado__in=['executando','incerta']).exists():
        raise ContaConflict('Há operações fiscais em andamento ou de resultado incerto. Concilie as notas antes de alterar o ambiente.')


def validar_certificado(data,password):
    try:
        key,cert,_=pkcs12.load_key_and_certificates(data,password.encode() if password else None)
        now=datetime.now(dt_timezone.utc)
        if not isinstance(key,RSAPrivateKey) or cert is None or not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
            raise ValueError
        if key.public_key().public_numbers()!=cert.public_key().public_numbers():raise ValueError
    except Exception:
        raise ValidationError({'certificado':'Não foi possível validar o PKCS#12. Confira a senha, a chave privada RSA e a validade do certificado.'})


def auditar(obj,user,changes):
    if not changes:return
    from auditlog.models import LogEntry
    LogEntry.objects.log_create(obj,action=LogEntry.Action.UPDATE,changes=changes,actor=user,serialized_data=None)


def salvar_ambiente(serializer,user,empresa):
    obj=serializer.instance
    periodo_seguro(empresa)
    values=dict(serializer.validated_data)
    confirmed=values.pop('confirmar_producao',False)
    production=not values.get('homologacao',obj.homologacao if obj else True)
    if production and (obj is None or obj.homologacao) and not confirmed:
        raise ValidationError({'confirmar_producao':'Confirme explicitamente a mudança para produção.'})
    password=values.get('senha',obj.senha if obj else '')
    # Campo vazio preserva a senha existente. Para um certificado sem senha, o PKCS#12
    # precisa ser reenviado e validado explicitamente com esse campo vazio.
    if obj and values.get('senha')=='' and 'certificado' not in values:
        values.pop('senha');password=obj.senha
    file=values.get('certificado')
    if file:
        validar_certificado(file.read(),password);file.seek(0)
    elif 'senha' in values:
        path=certificate_path(obj) if obj else None
        if path is None:raise ValidationError({'senha':'Envie o certificado junto da senha para validar a credencial.'})
        validar_certificado(path.read_bytes(),password)
    changes={key:[str(getattr(obj,key,None)) if obj else None,str(value)] for key,value in values.items() if key not in ('senha','certificado') and (obj is None or getattr(obj,key)!=value)}
    if 'senha' in values:changes['senha_alterada']=[False,True]
    if file:changes['certificado_substituido']=[False,True]
    try:
        if obj:
            for key,value in values.items():setattr(obj,key,value)
            obj.clean();obj.save()
        else:
            history=Nota.objects.filter(empresa_id=empresa).aggregate(lote=Max('numero_lote'),rps=Max('numero_rps'))
            obj=Ambiente(empresa_id=empresa,senha=values.pop('senha',''),numero_lote=str(history['lote'] or 0),numero_rps=str(history['rps'] or 0),**values)
            obj.clean();obj.save()
        auditar(obj,user,changes)
    except Exception:
        # Somente o arquivo recém-gravado é elegível a limpeza em falha; arquivos antigos ficam preservados.
        if file and obj and obj.certificado and obj.certificado._committed:
            obj.certificado.storage.delete(obj.certificado.name)
        raise
    serializer.instance=obj
    return obj


def ajustar_sequencias(obj,user,lote,rps):
    periodo_seguro(obj.empresa_id)
    history=Nota.objects.filter(empresa_id=obj.empresa_id).aggregate(lote=Max('numero_lote'),rps=Max('numero_rps'))
    try:
        minimum_batch=max(int(obj.numero_lote or 0),history['lote'] or 0)
        minimum_rps=max(int(obj.numero_rps or 0),history['rps'] or 0)
    except ValueError:raise ContaConflict('Há contadores legados inválidos. Revise o histórico antes de ajustar.')
    if lote<minimum_batch or rps<minimum_rps:
        raise ValidationError({'sequencias':'Não é permitido reduzir as sequências nem ficar abaixo dos números já reservados nas notas.'})
    changes={'numero_lote':[obj.numero_lote,str(lote)],'numero_rps':[obj.numero_rps,str(rps)]}
    obj.numero_lote,obj.numero_rps=str(lote),str(rps);obj.clean();obj.save(update_fields=['numero_lote','numero_rps']);auditar(obj,user,changes)
    return obj
