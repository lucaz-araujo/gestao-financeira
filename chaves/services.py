import hashlib
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError,PermissionDenied
from conta.services import ContaConflict
from clientes.models import Cliente
from servicos.models import Servico
from .models import ChaveServico


def chave_legada(servico,cliente,competencia,exercicio):
    if not cliente.cnpj:
        raise ValidationError({'cliente':'Informe o CNPJ do cliente antes de gerar a chave de serviço.'})
    payload = str(servico.descricao)+str(cliente.cnpj)+str(competencia).zfill(2)+str(exercicio)+settings.API_SECRET_KEY
    try:
        encoded = payload.encode('ascii')
    except UnicodeEncodeError:
        raise ValidationError({'servico':'A integração legada exige descrição de serviço sem caracteres fora de ASCII. Revise o serviço antes de gerar a chave.'})
    return hashlib.md5(encoded).hexdigest()


@transaction.atomic
def gravar_chave(serializer,usuario,empresa):
    old = serializer.instance
    values = serializer.validated_data
    service = values.get('servico',old.servico if old else None)
    client = values.get('cliente',old.cliente if old else None)
    service = Servico.objects.select_for_update().get(pk=service.pk)
    client = Cliente.objects.select_for_update().get(pk=client.pk)
    if client.empresa_id != empresa or service.empresa_id != empresa or (usuario.uf_id and client.uf_id != usuario.uf_id):
        raise PermissionDenied('Cliente ou serviço fora do escopo autorizado.')
    month = values.get('competencia',old.competencia if old else None)
    year = values.get('exercicio',old.exercicio if old else None)
    candidate = ChaveServico(cliente=client,servico=service,competencia=month,exercicio=year)
    candidate.clean()
    # O bloqueio do cliente serializa chaves da mesma competência mesmo sem índice legado composto.
    if ChaveServico.objects.filter(cliente=client,servico=service,competencia=month,exercicio=year).exclude(pk=old.pk if old else None).exists():
        raise ContaConflict('Esta competência já possui uma chave para o cliente e serviço.')
    key = chave_legada(service,client,month,year)
    if ChaveServico.objects.filter(chave=key).exclude(pk=old.pk if old else None).exists():
        raise ContaConflict('A chave calculada já pertence a outro registro. Revise os vínculos e os dados do cliente.')
    return serializer.save(cliente=client,servico=service,competencia=month,exercicio=year,chave=key,usuario=usuario,dt_liberacao=timezone.now())
