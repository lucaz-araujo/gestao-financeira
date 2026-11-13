# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from django.db import models
from django.core.exceptions import ValidationError
from contratos.models import Contrato
from usuario.models import Usuario
from produtos.models import Produto
import hashlib
from django.conf import settings

TP_PESSOA = (('PF', 'Pessoa Física'), ('PJ', 'Pessoa Juridica'))


class Uf(models.Model):
    sigla = models.CharField(u'Sigle', max_length=5)
    descricao = models.CharField(u'Estado', max_length=60)
    codgio_ibge = models.CharField(u'IBGE', max_length=2, null=True)

    def __str__(self):
        return f'{self.sigla}'

    class Meta:
        ordering = ['sigla']
        verbose_name_plural = 'Ufs'


class Municipio(models.Model):
    uf = models.ForeignKey(Uf,
                           related_name='Municipios',
                           on_delete=models.PROTECT)
    codigo_ibge = models.CharField('IBGE', max_length=10)
    descricao = models.CharField('Município', max_length=100)

    def __str__(self):
        return f'{self.descricao}'

    class Meta:
        ordering = ['descricao']
        verbose_name_plural = 'Municipios'


class Parceiro(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    instituicao = models.CharField('Instituição', max_length=200, unique=True)
    cnpj = models.CharField('C.N.P.J.', max_length=20)
    gcf = models.CharField('C.G.F.', max_length=20)
    endereco = models.CharField('Endereço', max_length=60)
    numero = models.CharField('Número', max_length=10)
    bairro = models.CharField('bairro', max_length=60)
    cidade = models.ForeignKey(Municipio,
                               null=True,
                               on_delete=models.PROTECT)
    uf = models.ForeignKey(Uf,
                           null=True,
                           on_delete=models.PROTECT)
    cep = models.CharField('C.E.P.', max_length=15)
    site = models.CharField('Site', max_length=200, null=True)
    tipo_pessoa = models.CharField(choices=TP_PESSOA, max_length=2, default='PJ')
    resp_nome = models.CharField('Nome', max_length=60, null=True)
    resp_cargo = models.CharField('Cargo', max_length=60, null=True)
    resp_cpf = models.CharField('C.P.F.', max_length=20, null=True)
    dt_resp_nascimento = models.DateField('Nascimento', null=True)
    resp_telefone = models.CharField('Telefone', max_length=20, null=True)
    resp_email = models.EmailField('email', max_length=100, null=True)
    excecao = models.BooleanField('Exeção', default=False)

    libera_clientes = models.BooleanField('Bloqueia Clientes', default=True)
    dt_data_limite = models.DateField('Data Limite', null=True, blank=True)

    def __str__(self):
        return f'{self.instituicao}'

    class Meta:
        ordering = ['instituicao']
        verbose_name_plural = 'Parceiros'


class Cliente(models.Model):
    empresa = models.ForeignKey('empresa.Empresa',
                                null=True,
                                on_delete=models.PROTECT)
    parceiro = models.ForeignKey(Parceiro,
                                 null=True,
                                 related_name='par_clientes',
                                 on_delete=models.PROTECT)
    instituicao = models.CharField('Instituição', max_length=200)
    cnpj = models.CharField('C.N.P.J.', max_length=20, null=True)
    gcf = models.CharField('C.G.F.', max_length=20, null=True)
    endereco = models.CharField('Endereço', max_length=100, null=True)
    numero = models.CharField('Número', max_length=10, null=True)
    bairro = models.CharField('bairro', max_length=60, null=True)
    uf = models.ForeignKey(Uf,
                           null=True,
                           on_delete=models.PROTECT)
    cidade = models.ForeignKey(Municipio,
                               null=True,
                               blank=True,
                               on_delete=models.PROTECT)
    banco = models.ForeignKey('conta.Banco',
                              null=True,
                              blank=True,
                              on_delete=models.PROTECT)
    agencia = models.CharField('Agència', max_length=10, null=True, blank=True)
    cep = models.CharField('C.E.P.', max_length=15, null=True)
    site = models.CharField('Site', max_length=200, null=True)
    tipo_pessoa = models.CharField(choices=TP_PESSOA, max_length=2, default='PJ')
    resp_nome = models.CharField('Nome do responsável', max_length=60, null=True)
    resp_cargo = models.CharField('Cargo', max_length=100, null=True)
    resp_cpf = models.CharField('C.P.F.', max_length=20, null=True)
    dt_resp_nascimento = models.DateField('Nascimento', null=True)
    resp_telefone = models.CharField('Telefone', max_length=20, null=True)
    resp_email = models.CharField('email', max_length=200, null=True)
    codigolayout = models.CharField('Layout', max_length=10, null=True)
    codigoentidade = models.CharField('Entidade', max_length=10, null=True)
    codigosim = models.CharField('Sim', max_length=10, null=True)
    codigoold = models.CharField('Código Antigo', max_length=10, null=True)
    codigotcm = models.CharField('Código TCM', max_length=10, null=True)
    senhatcm = models.CharField('Senha TCM', max_length=10, null=True)
    usertcm = models.CharField('Usuário TCM', max_length=10, null=True)
    ativo = models.BooleanField('Ativo', default=True)
    libera_tcm = models.BooleanField('Ativo', default=True)
    libera_pagonline = models.BooleanField('Ativo', default=True)
    libera_sistema = models.BooleanField('Ativo', default=True)
    desativar = models.BooleanField('Ativo', default=False)
    observacoes = models.TextField(null=True, blank=True)
    numero_conta = models.CharField(max_length=15, null=True, blank=True)
    token = models.CharField(max_length=100, null=True, blank=True)

    # Bloqueios individuais
    libera_transparencia = models.BooleanField('Transparência', default=True)
    libera_contracheque = models.BooleanField('Contra-Cheque', default=True)
    gerar_notas = models.BooleanField('Contra-Cheque', default=True)

    def __str__(self):
        return u'{0}'.format(self.instituicao)

    def contratos_ativos(self):
        contratos=Contrato.objects.filter(cliente=self, ativo=True)
        return contratos

    def produtos(self):
        lista = []
        contrato = Contrato.objects.filter(cliente=self, ativo=True)
        if contrato.last():
            for p in contrato.last().produtosCont.all():
                lista.append({'produtos': p.produtos.sigla, 'valor': p.produtos.valor})
        return lista

    def list_email(self):
        ret = ''
        lista = '{}'.format(self.resp_email).split(',')
        if lista is None:
            lista = '{}'.format(self.resp_email).split(';')
        if lista is None:
            lista = '{}'.format(self.resp_email).split(' ')
        for em in lista:
            ret += '{}\n'.format(em)
        return ret


    def save(self, *args, **kwargs):
        if self.token is None:
            vhash = bytes(u'{0}'.format(self.instituicao), 'utf-8')
            self.token = hashlib.sha256(vhash).hexdigest()
        super(Cliente, self).save(*args, **kwargs)

    class Meta:
        ordering = ['instituicao']
        verbose_name_plural = 'Clientes'


class Liberacao(models.Model):
    cliente = models.ForeignKey(Cliente,
                                related_name='liberacao',
                                null=True,
                                on_delete=models.PROTECT)
    competencia = models.CharField(max_length=2)
    exercicio = models.IntegerField(default=2018)
    produto = models.ForeignKey(Produto,
                                null=True,
                                on_delete=models.PROTECT)
    dt_liberacao = models.DateTimeField()
    chave = models.CharField(max_length=100, unique=True)
    codigo = models.CharField(max_length=4, default='PM01')
    codigo_layout = models.CharField(max_length=4, default='0000')
    usuario = models.ForeignKey(Usuario,
                                null=True,
                                on_delete=models.PROTECT)

    def __str__(self):
        return u'{0}'.format(self.competencia)

    def atualizar_chave(self):
        """Preserva o protocolo utilizado pelos consumidores Delphi."""
        cliente = self.cliente
        if not cliente or not cliente.codigolayout or not cliente.codigoentidade:
            raise ValidationError({'cliente': 'Informe os códigos Layout e entidade no cliente.'})
        if len(cliente.codigolayout) > 4 or len(cliente.codigoentidade) > 4:
            raise ValidationError({'cliente': 'Os códigos da liberação comportam até quatro caracteres.'})
        self.codigo_layout = cliente.codigolayout
        self.codigo = cliente.codigoentidade
        payload = (f'{self.codigo_layout}{self.codigo}{self.competencia}'
                   f'{self.exercicio}sucesso{settings.API_SECRET_KEY}')
        try:
            self.chave = hashlib.md5(payload.encode('ascii')).hexdigest()
        except UnicodeEncodeError:
            raise ValidationError({'cliente': 'Os códigos da liberação devem conter somente caracteres ASCII.'})

    def integro(self):
        return ((hashlib.md5(bytes(str(self.cliente_id) +
                                   str(self.codigo_layout) +
                                   str(self.competencia) +
                                   str(self.codigo) +
                                   str(self.exercicio) +
                                   str(self.usuario_id) +
                                   str(self.dt_liberacao) +
                                   settings.API_SECRET_KEY, 'ascii')).hexdigest() == self.chave) and self.chave != None)

    class Meta:
        ordering = ['competencia']
        verbose_name_plural = 'Liberacoes'
        unique_together = (('cliente', 'codigo_layout', 'codigo', 'competencia', 'exercicio',), )


class LiberacaoDatas(models.Model):
    cliente = models.ForeignKey(Cliente,
                                related_name='liberacaodata',
                                null=True,
                                on_delete=models.PROTECT)
    usuario = models.ForeignKey(Usuario,
                                null=True,
                                on_delete=models.PROTECT)

    # Bloqueios individuais
    dt_ate = models.DateField('Data Inicial',null=True)
    dt_aparte = models.DateField('Data Final',null=True)
    libera_tcm = models.BooleanField('Libera TCM', default=False)
    libera_pagonline = models.BooleanField('Libera pagamento On-Line', default=False)
    libera_sistema = models.BooleanField('Libera sistema', default=False)
    desativar = models.BooleanField('Desativar', default=False)
    libera_transparencia = models.BooleanField('Liberar transparência', default=False)
    libera_contracheque = models.BooleanField('Liberar contra-Cheque', default=False)
    gerar_notas = models.BooleanField('Liberar gerar notas', default=False)

    def __str__(self):
        return '{}'.format(self.dt_ate)

    def clean(self):
        super().clean()
        errors = {}
        if not self.dt_ate:
            errors['dt_ate'] = 'Informe a data inicial.'
        if not self.dt_aparte:
            errors['dt_aparte'] = 'Informe a data final.'
        if self.dt_ate and self.dt_aparte and self.dt_ate > self.dt_aparte:
            errors['dt_aparte'] = 'A data final deve ser igual ou posterior à inicial.'
        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name_plural = 'LiberacaoDatas'


class MunicipioBr(models.Model):
    cdmunic = models.CharField(max_length=4, null=True)
    ufmuni = models.CharField(max_length=2, null=True)
    cidade = models.CharField(max_length=30, null=True)
    cdtrib = models.CharField(max_length=3, null=True)
    ttvere2009 = models.CharField(max_length=3, null=True)

    def __str__(self):
        return '{}'.format(self.cdmunic)

    class Meta:
        ordering = ['cidade']
        verbose_name_plural = 'MunicipiosBr'
