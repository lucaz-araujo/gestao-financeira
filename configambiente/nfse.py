# -*- coding: utf-8 -*-
from decimal import Decimal
from configambiente.models import Ambiente
from layCliente import settings
from notas.models import Nota
from pynfe.entidades.cliente import Cliente
from pynfe.entidades.emitente import Emitente
from pynfe.entidades.notafiscal import NotaFiscalServico
from pynfe.entidades.servico import Servico
try:
    from pynfe.processamento.assinatura import AssinaturaA1
    from pynfe.processamento.comunicacao import ComunicacaoNfse, ComunicacaoSefaz
    from pynfe.processamento.serializacao import SerializacaoNfse
except ModuleNotFoundError as exc:
    if not exc.name or not exc.name.startswith('pyxb'):
        raise

    class _MissingFiscalDependency:
        def __init__(self, error):
            self.error = error

        def __call__(self, *args, **kwargs):
            raise RuntimeError(
                'A dependência PyXB é necessária para transmitir documentos fiscais.'
            ) from self.error

    AssinaturaA1 = ComunicacaoNfse = ComunicacaoSefaz = SerializacaoNfse = (
        _MissingFiscalDependency(exc)
    )
from pynfe.utils.flags import CODIGO_BRASIL

AUTORIZADOR = 'speedgov'


class Nfse:
    certificado = ''
    senha = ''
    homologacao = True
    autorizador = AUTORIZADOR
    aliquota_iss = 0
    NumeroLote = 0

    nota = Nota()
    conf = None

    cliente = Cliente()
    servico = Servico()
    notaServ = NotaFiscalServico()

    def __init__(self, nota):
        # Cada requisição possui suas próprias entidades e configuração de empresa.
        self.cliente = Cliente()
        self.servico = Servico()
        self.notaServ = NotaFiscalServico()
        self.conf = Ambiente.objects.select_related('empresa').get(empresa_id=nota.empresa_id)
        self.nota = nota
        self.emitente = Emitente(
            cnpj=''.join(c for c in self.conf.empresa.cnpj if c.isdigit()),
            inscricao_municipal=self.conf.empresa.inscricao_municipal
        )

        from notas.gateway import certificate_path
        self.certificado = str(certificate_path(self.conf) or '')
        self.senha = self.conf.senha
        self.homologacao = self.conf.homologacao
        self.aliquota_iss = self.conf.aliquota_iss
        self.NumeroLote = self.conf.numero_lote

    def EnviarNfse(self):
        # tomador
        self.cliente.razao_social = self.nota.contrato.cliente.instituicao
        self.cliente.tipo_documento = 'CNPJ'  # CPF ou CNPJ
        self.cliente.numero_documento = self.nota.contrato.cliente.cnpj.replace('.', '').replace('/', '').replace('-',
                                                                                                                  '')  # apenas os numero do CPF ou CNPJ
        if self.nota.contrato.cliente.gcf:
            self.cliente.inscricao_municipal = self.nota.contrato.cliente.gcf.replace('.', '').replace('/', '').replace(
                '-', '')  # opcional
        self.cliente.endereco_logradouro = self.nota.contrato.cliente.endereco
        self.cliente.endereco_numero = self.nota.contrato.cliente.numero
        self.cliente.endereco_complemento = ''  # opcional
        self.cliente.endereco_bairro = self.nota.contrato.cliente.bairro
        self.cliente.endereco_cod_municipio = self.nota.contrato.cliente.cidade.codigo_ibge
        self.cliente.endereco_uf = self.nota.contrato.cliente.uf.sigla
        self.cliente.endereco_cep = self.nota.contrato.cliente.cep.replace('.', '').replace('/', '').replace('-', '')
        self.cliente.endereco_pais = CODIGO_BRASIL
        self.cliente.endereco_telefone = (self.nota.contrato.cliente.resp_telefone or '').replace('(', '').replace(')',
                                                                                                           '').replace(
            '-', '').replace(' ', '')
        self.cliente.email = (self.nota.contrato.cliente.resp_email or '')[:80]  # opcional

        # serviço
        self.servico.valor_servico = format(self.nota.valor_bruto, '018.2f')
        self.servico.iss_retido = 2  # 1 - Sim; 2 - Não
        self.servico.item_lista = self.nota.coigo_servico
        self.servico.discriminacao = self.nota.texto_nota
        self.servico.codigo_municipio = self.nota.cidade.codigo_ibge

        # Dados opcionais
        self.servico.codigo_cnae = self.nota.codigo_cnae
        self.servico.codigo_tributacao_municipio = self.nota.codigo_tributacao_municipio
        self.servico.valor_deducoes = Decimal('0.00')
        self.servico.valor_pis = Decimal('0.00')
        self.servico.valor_confins = Decimal('0.00')
        self.servico.valor_inss = Decimal('0.00')
        self.servico.valor_ir = Decimal('0.00')
        self.servico.valor_csll = Decimal('0.00')
        self.servico.valor_iss = format(self.nota.imposto, '018.2f')
        self.servico.valor_iss_retido = Decimal('0.00')
        self.servico.valor_liquido = format(self.nota.valor_liquido, '018.2f')
        self.servico.outras_retencoes = Decimal('0.00')
        self.servico.base_calculo = format(self.nota.valor_bruto, '018.2f')
        self.servico.aliquota = format(self.nota.aliq_imposto if self.nota.aliq_imposto is not None else self.aliquota_iss, '08.2f')
        self.servico.desconto_incondicionado = Decimal('0.00')
        self.servico.desconto_condicionado = Decimal('0.00')

        # nota
        if self.nota.numero_rps is None or self.nota.numero_lote is None:
            raise ValueError('Reserve o RPS e o lote antes de transmitir.')
        self.notaServ.identificador = self.nota.numero_rps
        self.notaServ.data_emissao = self.nota.dt_data_emissao
        self.notaServ.servico = self.servico
        self.notaServ.emitente = self.emitente
        self.notaServ.cliente = self.cliente

        # Optante Simples Nacional
        self.notaServ.simples = 2  # 1-Sim; 2-Não
        self.notaServ.natureza_operacao = 1
        self.notaServ.incentivo = 2  # Incentivador Cultural # 1-Sim; 2-Não
        self.notaServ.serie = 'A1'
        self.notaServ.tipo = '1'
        self.NumeroLote = self.nota.numero_lote

        # serialização
        serializador = SerializacaoNfse(AUTORIZADOR)
        xml = serializador.gerar_lote(self.notaServ)

        xml = xml.replace('.0<', '.00<')
        xml = xml.replace('.1<', '.10<')
        xml = xml.replace('.2<', '.20<')
        xml = xml.replace('.3<', '.30<')
        xml = xml.replace('.4<', '.40<')
        xml = xml.replace('.5<', '.50<')
        xml = xml.replace('.6<', '.60<')
        xml = xml.replace('.7<', '.70<')
        xml = xml.replace('.8<', '.80<')
        xml = xml.replace('.9<', '.90<')

        xml = xml.replace('ns1', 'p')
        xml = xml.replace('ns2', 'p1')

        # troca cabeçalho do xml
        xml = xml.replace(
            'xmlns:p="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd" xmlns:p1="http://ws.speedgov.com.br/tipos_v1.xsd"'
            ,
            'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:p="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd" xmlns:p1="http://ws.speedgov.com.br/tipos_v1.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd enviar_lote_rps_envio_v1.xsd "')

        xml = xml.replace('<p1:NumeroLote>0</p1:NumeroLote>',
                          '<p1:NumeroLote>%s</p1:NumeroLote>' % (self.nota.numero_lote))
        xml = xml.replace('Id="1">', 'Id="%s">' % (self.nota.numero_lote))

        # assinatura
        a1 = AssinaturaA1(self.certificado, self.senha, AUTORIZADOR)
        xml = a1.assinarLote(xml)

        # envio
        con = ComunicacaoNfse(self.certificado, self.senha, AUTORIZADOR, self.homologacao)
        envio = con.enviar_lote(xml)

        return envio

    def CancelarNfse(self, nota):
        # prestador
        emitente = Emitente(
            cnpj=''.join(c for c in self.conf.empresa.cnpj if c.isdigit()),
            inscricao_municipal=self.conf.empresa.inscricao_municipal
        )

        # nota
        nota = NotaFiscalServico(
            identificador=nota.numero,  # número da nfs-e
            emitente=emitente
        )

        # serializar
        serializador = SerializacaoNfse(self.autorizador)
        xml = serializador.cancelar(nota)

        xml = xml.replace('ns1', 'p')
        xml = xml.replace('ns2', 'p1')

        # troca cabeçalho do xml
        xml = xml.replace(
            'xmlns:p="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd" xmlns:p1="http://ws.speedgov.com.br/tipos_v1.xsd"'
            ,
            'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:p="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd" xmlns:p1="http://ws.speedgov.com.br/tipos_v1.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd enviar_lote_rps_envio_v1.xsd "')

        # # assinatura
        # a1 = AssinaturaA1(self.certificado, self.senha, self.autorizador)
        # xml = a1.assinarCancelar(xml)

        con = ComunicacaoNfse(self.certificado, self.senha, self.autorizador, self.homologacao)
        resposta = con.cancelar(xml)

        return (resposta)

    def ConsultaNfse(self, nota):
        xml = SerializacaoNfse(self.autorizador).consultar_nfse(self.emitente, nota.numero)
        xml = xml.replace('ns1', 'p').replace('ns2', 'p1')
        # O XSD de consulta por número não admite o elemento Signature.
        con = ComunicacaoNfse(self.certificado, self.senha, self.autorizador, self.homologacao)
        return con.consultar(xml)

    def ConsultaRps(self, nota):
        xml = SerializacaoNfse(self.autorizador).consultar_rps(self.emitente, nota.numero_rps, 'A1', '1')
        xml = xml.replace('ns1', 'p').replace('ns2', 'p1')
        # O XSD de consulta por RPS não admite o elemento Signature.
        con = ComunicacaoNfse(self.certificado, self.senha, self.autorizador, self.homologacao)
        return con.consultar_rps(xml)

    def ConsultaLoteNfse(self, nota):
        # prestador
        emitente = Emitente(
            cnpj=''.join(c for c in self.conf.empresa.cnpj if c.isdigit()),
            inscricao_municipal=self.conf.empresa.inscricao_municipal
        )

        serializador = SerializacaoNfse(self.autorizador)
        nfse = serializador.consultar_lote(emitente, nota.protocolo_envio)

        nfse = nfse.replace('ns1', 'p')
        nfse = nfse.replace('ns2', 'p1')

        # troca cabeçalho do xml
        nfse = nfse.replace(
            'xmlns:p="http://ws.speedgov.com.br/consultar_lote_rps_envio_v1.xsd" xmlns:p1="http://ws.speedgov.com.br/tipos_v1.xsd"'
            ,
            'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:p="http://ws.speedgov.com.br/consultar_lote_rps_envio_v1.xsd" xmlns:p1="http://ws.speedgov.com.br/tipos_v1.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://ws.speedgov.com.br/consultar_lote_rps_envio_v1.xsd consultar_lote_rps_envio_v1.xsd "')

        a1 = AssinaturaA1(self.certificado, self.senha, self.autorizador)
        nfse = a1.assinarConsultaLote(nfse, retorna_string=True)


        con = ComunicacaoNfse(self.certificado, self.senha, self.autorizador, self.homologacao)
        resposta = con.consultar_lote(nfse)

        return (resposta)

    def autorizarNfse(self, nota):
        # prestador
        emitente = Emitente(
            cnpj=''.join(c for c in self.conf.empresa.cnpj if c.isdigit()),
            inscricao_municipal=self.conf.empresa.inscricao_municipal
        )

        serializador = SerializacaoNfse(self.autorizador)
        nfse = serializador.consultar_nfse(emitente, nota.numero)

        nfse = nfse.replace('ns1', 'p')
        nfse = nfse.replace('ns2', 'p1')

        # troca cabeçalho do xml
        nfse = nfse.replace(
            'xmlns:p="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd" xmlns:p1="http://ws.speedgov.com.br/tipos_v1.xsd"'
            ,
            'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:p="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd" xmlns:p1="http://ws.speedgov.com.br/tipos_v1.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd enviar_lote_rps_envio_v1.xsd "')

        # a1 = AssinaturaA1(self.certificado, self.senha, self.autorizador)
        # xml = a1.assinarConsulta(nfse, retorna_string=True)

        con = ComunicacaoNfse(self.certificado, self.senha, self.autorizador, self.homologacao)
        resposta = con.autorizacao(xml)

        return (resposta)

    def ConsultaSituacaoLote(self, nota):
        # prestador
        emitente = Emitente(
            cnpj=''.join(c for c in self.conf.empresa.cnpj if c.isdigit()),
            inscricao_municipal=self.conf.empresa.inscricao_municipal
        )

        serializador = SerializacaoNfse(self.autorizador)
        xml = serializador.consultar_situacao_lote(emitente, nota.protocolo_envio)

        xml = xml.replace('ns1', 'p')
        xml = xml.replace('ns2', 'p1')

        # troca cabeçalho do xml
        xml = xml.replace(
            'xmlns:p="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd" xmlns:p1="http://ws.speedgov.com.br/tipos_v1.xsd"'
            ,
            'xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:p="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd" xmlns:p1="http://ws.speedgov.com.br/tipos_v1.xsd" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://ws.speedgov.com.br/enviar_lote_rps_envio_v1.xsd enviar_lote_rps_envio_v1.xsd "')

        # a1 = AssinaturaA1(self.certificado, self.senha, self.autorizador)
        # xml = a1.assinarConsultaLote(xml, retorna_string=True)

        con = ComunicacaoNfse(self.certificado, self.senha, self.autorizador, self.homologacao)
        resposta = con.consultar_situacao_lote(xml)

        return (resposta)

    def ServicoNfse(self, uf):
        con = ComunicacaoSefaz(uf, self.certificado, self.senha, self.homologacao)
        xml = con.status_servico('nfce')  # nfe ou nfce
        print(xml.text)
