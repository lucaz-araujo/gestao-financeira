# -*- coding: utf-8 -*-

from pynfe.utils import etree, remover_acentos
import subprocess
import tempfile
from pathlib import Path


class Assinatura(object):
    """Classe abstrata responsavel por definir os metodos e logica das classes
    de assinatura digital."""

    certificado = None
    senha = None

    def __init__(self, certificado, senha, autorizador=None):
        self.certificado = certificado
        self.senha = senha
        self.autorizador = autorizador
        self._tmp = tempfile.TemporaryDirectory(prefix='gestao-nfse-')

    def _file(self, name):
        return str(Path(self._tmp.name) / name)

    def _certificate_info(self, keyinfo):
        # Identifica explicitamente a única chave carregada pelo XMLSec 1.3.
        etree.SubElement(keyinfo, 'KeyName').text = 'gestao-nfse'
        etree.SubElement(keyinfo, 'X509Data')

    def assinar(self, xml):
        """Efetua a assinatura da nota"""
        pass


class AssinaturaA1(Assinatura):
    """Classe responsavel por efetuar a assinatura do certificado
    digital no XML informado."""

    def assinar(self, xml, retorna_string=False):
        try:
            # No raiz do XML de saida
            tag = 'infNFe'  # tag que será assinada
            raiz = etree.Element('Signature', xmlns='http://www.w3.org/2000/09/xmldsig#')
            siginfo = etree.SubElement(raiz, 'SignedInfo')
            etree.SubElement(siginfo, 'CanonicalizationMethod', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
            etree.SubElement(siginfo, 'SignatureMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#rsa-sha1')
            # Tenta achar a tag infNFe
            try:
                ref = etree.SubElement(siginfo, 'Reference', URI='#'+xml.findall('infNFe')[0].attrib['Id'])
            # Caso nao tenha a tag infNFe, procura a tag infEvento
            except IndexError:
                tag = 'infEvento'
                ref = etree.SubElement(siginfo, 'Reference', URI='#'+xml.findall('infEvento')[0].attrib['Id'])
            trans = etree.SubElement(ref, 'Transforms')
            etree.SubElement(trans, 'Transform', Algorithm='http://www.w3.org/2000/09/xmldsig#enveloped-signature')
            etree.SubElement(trans, 'Transform', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
            etree.SubElement(ref, 'DigestMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#sha1')
            etree.SubElement(ref, 'DigestValue')
            etree.SubElement(raiz, 'SignatureValue')
            keyinfo = etree.SubElement(raiz, 'KeyInfo')
            self._certificate_info(keyinfo)

            xml.append(raiz)

            # Escreve no arquivo depois de remover caracteres especiais e parse string
            with open(self._file('testes.xml'), 'w') as arquivo:
                arquivo.write(remover_acentos(etree.tostring(xml, encoding="unicode", pretty_print=False)))

            subprocess.run(['xmlsec1', '--sign', '--pkcs12:gestao-nfse', self.certificado, '--pwd', self.senha, '--crypto', 'openssl', '--output', self._file('funfa.xml'), '--id-attr:Id', tag, self._file('testes.xml')], check=True, capture_output=True, timeout=30)
            xml = etree.parse(self._file('funfa.xml')).getroot()

            if retorna_string:
                return etree.tostring(xml, encoding="unicode", pretty_print=False)
            else:
                return xml
        except Exception as e:
            raise e

    def assinarNfse(self, xml, retorna_string=True):
        "Assina NFS-e"
        try:
            # define variaveis de acordo com autorizador
            if self.autorizador == 'ginfes':
                xpath = './/ns2:InfRps'
                tag = 'InfRps'
            elif self.autorizador == 'betha':
                xpath = './/ns1:InfDeclaracaoPrestacaoServico'
                tag = 'InfDeclaracaoPrestacaoServico'
            elif self.autorizador == 'speedgov':
                xpath = './/p1:InfRps'
                tag = 'InfRps'
            else:
                raise Exception('Autorizador não encontrado!')

            xml = etree.fromstring(xml)
            # define namespaces, pega do proprio xml
            namespaces = xml.nsmap
            # No raiz do XML de saida
            raiz = etree.Element('Signature', xmlns='http://www.w3.org/2000/09/xmldsig#')
            siginfo = etree.SubElement(raiz, 'SignedInfo')
            etree.SubElement(siginfo, 'CanonicalizationMethod', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
            etree.SubElement(siginfo, 'SignatureMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#rsa-sha1')
            # Tenta achar a tag
            ref = etree.SubElement(siginfo, 'Reference', URI='#' +
                                   xml.xpath(xpath, namespaces=namespaces)[0].attrib['Id'])
            trans = etree.SubElement(ref, 'Transforms')
            etree.SubElement(trans, 'Transform', Algorithm='http://www.w3.org/2000/09/xmldsig#enveloped-signature')
            etree.SubElement(trans, 'Transform', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
            etree.SubElement(ref, 'DigestMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#sha1')
            etree.SubElement(ref, 'DigestValue')
            etree.SubElement(raiz, 'SignatureValue')
            keyinfo = etree.SubElement(raiz, 'KeyInfo')
            self._certificate_info(keyinfo)

            rps = xml.xpath(xpath+'/..', namespaces=namespaces)[0]
            rps.append(raiz)

            # Escreve no arquivo depois de remover caracteres especiais e parse string
            with open(self._file('nfse.xml'), 'w') as arquivo:
                texto = remover_acentos(etree.tostring(xml, encoding="unicode", pretty_print=False))
                # se for tag do Betha
                if tag == 'InfDeclaracaoPrestacaoServico':
                    texto = texto.replace('ns1:', '').replace(':ns1', '')
                arquivo.write(texto)

            subprocess.run(['xmlsec1', '--sign', '--pkcs12:gestao-nfse', self.certificado,
                             '--pwd', self.senha, '--crypto', 'openssl', '--output',
                             self._file('nfse.xml'), '--id-attr:Id', tag, self._file('nfse.xml')], check=True, capture_output=True, timeout=30)

            if retorna_string:
                return open(self._file('nfse.xml'), 'r').read()
            else:
                return etree.parse(self._file('nfse.xml')).getroot()
        except Exception as e:
            raise e

    def assinarLote(self, xml, retorna_string=True):
        "Assina nfse e lote"
        try:
            xml = self.assinarNfse(xml, retorna_string=False)
            if self.autorizador == 'ginfes':
                xpath = './/ns1:LoteRps'
            elif self.autorizador == 'speedgov':
                xpath = './/p:LoteRps'
            tag = 'LoteRps'
            # define namespaces, pega do proprio xml
            namespaces = xml.nsmap
            # No raiz do XML de saida
            raiz = etree.Element('Signature', xmlns='http://www.w3.org/2000/09/xmldsig#')
            siginfo = etree.SubElement(raiz, 'SignedInfo')
            etree.SubElement(siginfo, 'CanonicalizationMethod', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
            etree.SubElement(siginfo, 'SignatureMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#rsa-sha1')
            # Tenta achar a tag
            ref = etree.SubElement(siginfo, 'Reference', URI='#' +
                                   xml.xpath(xpath, namespaces=namespaces)[0].attrib['Id'])
            trans = etree.SubElement(ref, 'Transforms')
            etree.SubElement(trans, 'Transform', Algorithm='http://www.w3.org/2000/09/xmldsig#enveloped-signature')
            etree.SubElement(trans, 'Transform', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
            etree.SubElement(ref, 'DigestMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#sha1')
            etree.SubElement(ref, 'DigestValue')
            etree.SubElement(raiz, 'SignatureValue')
            keyinfo = etree.SubElement(raiz, 'KeyInfo')
            self._certificate_info(keyinfo)

            # Posiciona a assinatura no destino final ANTES de assinar.
            # Mover a árvore assinada pode reconciliar prefixos e invalidar SignedInfo.
            base = xml.xpath(xpath+'/..', namespaces=namespaces)[0]
            base.append(raiz)

            # Escreve no arquivo depois de remover caracteres especiais
            with open(self._file('nfse.xml'), 'w') as arquivo:
                texto = remover_acentos(etree.tostring(xml, encoding="unicode", pretty_print=False))
                arquivo.write(texto)
            # assina lote
            subprocess.run(['xmlsec1', '--sign', '--pkcs12:gestao-nfse', self.certificado,
                             '--pwd', self.senha, '--crypto', 'openssl', '--output',
                             self._file('lote-assinado.xml'), '--id-attr:Id', tag,
                             '--node-xpath', '/*/*[local-name()="Signature"]', self._file('nfse.xml')], check=True, capture_output=True, timeout=30)

            if retorna_string:
                return Path(self._file('lote-assinado.xml')).read_text()
            return etree.parse(self._file('lote-assinado.xml')).getroot()
        except Exception as e:
            raise e

    def assinarCancelar(self, xml, retorna_string=True):
        """ Método que assina o xml para cancelamento de NFS-e """
        try:
            if self.autorizador == 'ginfes':
                xpath = 'CancelarNfseEnvio'
                tag = 'CancelarNfseEnvio'
                namespaces = {'ns1': 'http://www.ginfes.com.br/servico_cancelar_nfse_envio', 'ns2':'http://www.ginfes.com.br/tipos'}
            elif self.autorizador == 'betha':
                xpath = '/CancelarNfseEnvio/ns1:Pedido'
                tag = 'InfPedidoCancelamento'
                namespaces = {'ns1': 'http://www.betha.com.br/e-nota-contribuinte-ws'}
            elif self.autorizador == 'speedgov':
                    xpath = 'CancelarNfseEnvio'
                    tag = 'CancelarNfseEnvio'
                    namespaces = {'p1': 'http://ws.speedgov.com.br/cancelar_nfse_envio',
                                  'p2': 'http://ws.speedgov.com.br/tipos'}
            else:
                raise Exception('Autorizador não encontrado!')

            xml = etree.fromstring(xml)
            # No raiz do XML de saida
            raiz = etree.Element('Signature', xmlns='http://www.w3.org/2000/09/xmldsig#')
            siginfo = etree.SubElement(raiz, 'SignedInfo')
            etree.SubElement(siginfo, 'CanonicalizationMethod', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
            etree.SubElement(siginfo, 'SignatureMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#rsa-sha1')
            # Tenta achar a tag informada no xpath
            if tag == 'InfPedidoCancelamento':
                ref = etree.SubElement(siginfo, 'Reference', URI='#'+xml.xpath('.//ns1:'+tag, namespaces=namespaces)[0].attrib['Id'])
            # ginfes não tem id no cancelamento v2
            else:
                ref = etree.SubElement(siginfo, 'Reference', URI='')
            trans = etree.SubElement(ref, 'Transforms')
            etree.SubElement(trans, 'Transform', Algorithm='http://www.w3.org/2000/09/xmldsig#enveloped-signature')
            etree.SubElement(trans, 'Transform', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
            etree.SubElement(ref, 'DigestMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#sha1')
            etree.SubElement(ref, 'DigestValue')
            etree.SubElement(raiz, 'SignatureValue')
            keyinfo = etree.SubElement(raiz, 'KeyInfo')
            self._certificate_info(keyinfo)

            if tag == 'InfPedidoCancelamento':
                xml = xml.xpath(xpath, namespaces=namespaces)[0]
            # ginfes só possui a tag root
            else:
               xml.append(raiz)

            # Escreve no arquivo depois de remover caracteres especiais e parse string
            with open(self._file('nfse.xml'), 'w') as arquivo:
                arquivo.write(remover_acentos(etree.tostring(xml, encoding="unicode", pretty_print=False).replace('\n','')))

            subprocess.run(['xmlsec1', '--sign', '--pkcs12:gestao-nfse', self.certificado, '--pwd', self.senha, '--crypto', 'openssl', '--output', self._file('funfa.xml'), '--id-attr:Id', tag, self._file('nfse.xml')], check=True, capture_output=True, timeout=30)

            if retorna_string:
                return open(self._file('funfa.xml'), 'r').read()
            else:
                return etree.parse(self._file('funfa.xml')).getroot()
        except Exception as e:
            raise e

    def assinarConsulta(self, xml, retorna_string=True):
        if self.autorizador == 'ginfes':
            vant = 'ns1'
        elif self.autorizador == 'speedgov':
            vant = 'p'
        else:
            vant = 'ns1'
        tag = vant+':ConsultarNfseEnvio'
        return self._assinar(xml, tag, retorna_string)


    def assinarConsultaLote(self, xml, retorna_string=True, situacao=False):
        if self.autorizador == 'ginfes':
            vant='ns1'
        elif self.autorizador == 'speedgov':
            vant = 'p'
        else:
            vant = 'ns1'
        if situacao:
            tag = vant+':ConsultarSituacaoLoteRpsEnvio'
        else:
            tag = vant+':ConsultarLoteRpsEnvio'
        return self._assinar(xml, tag, retorna_string)

    def assinarConsultaRps(self, xml, retorna_string=True):
        if self.autorizador == 'ginfes':
            vant = 'ns1'
        elif self.autorizador == 'speedgov':
            vant = 'p'
        else:
            vant = 'ns1'
        tag = vant+':ConsultarNfseRpsEnvio'
        return self._assinar(xml, tag, retorna_string)

    def _assinar(self, xml, tag, retorna_string=True):
        """ Método para assinar xml de NFS-e com tags sem ID
            Consulta de Lote e Consulta por RPS
            @param tag - raiz do xml que será assinado
        """
        try:
            xml = etree.fromstring(xml)
            # No raiz do XML de saida
            raiz = etree.Element('Signature', xmlns='http://www.w3.org/2000/09/xmldsig#')
            siginfo = etree.SubElement(raiz, 'SignedInfo')
            etree.SubElement(siginfo, 'CanonicalizationMethod', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
            etree.SubElement(siginfo, 'SignatureMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#rsa-sha1')
            # Consulta nao tem id
            ref = etree.SubElement(siginfo, 'Reference', URI='')

            trans = etree.SubElement(ref, 'Transforms')
            etree.SubElement(trans, 'Transform', Algorithm='http://www.w3.org/2000/09/xmldsig#enveloped-signature')
            etree.SubElement(trans, 'Transform', Algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315')
            etree.SubElement(ref, 'DigestMethod', Algorithm='http://www.w3.org/2000/09/xmldsig#sha1')
            etree.SubElement(ref, 'DigestValue')
            etree.SubElement(raiz, 'SignatureValue')
            keyinfo = etree.SubElement(raiz, 'KeyInfo')
            self._certificate_info(keyinfo)

            xml.append(raiz)

            # Escreve no arquivo depois de remover caracteres especiais e parse string
            with open(self._file('nfse.xml'), 'w') as arquivo:
                arquivo.write(remover_acentos(etree.tostring(xml, encoding="unicode", pretty_print=False).replace('\n','')))

            subprocess.run(['xmlsec1', '--sign', '--pkcs12:gestao-nfse', self.certificado, '--pwd', self.senha, '--crypto', 'openssl', '--output', self._file('funfa.xml'), '--id-attr:Id', tag, self._file('nfse.xml')], check=True, capture_output=True, timeout=30)
            xml = etree.parse(self._file('funfa.xml')).getroot()

            if retorna_string:
                return etree.tostring(xml, encoding="unicode", pretty_print=False).replace('\n','')
            else:
                return xml
        except Exception as e:
            raise e
