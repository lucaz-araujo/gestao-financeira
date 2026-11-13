# -*- coding: utf-8 -*-
import re
from django.db import models
from django.core import validators
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


class UserManager(BaseUserManager):
    
    def _create_user(self, username, email, password, is_staff, is_superuser, **extra_fields):
        now = timezone.now()
        if not username:
            raise ValueError(_('The given username must be set'))
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, is_staff=is_staff, is_active=True,
                          is_superuser=is_superuser, last_login=now, date_joined=now, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None,  **extra_fields):
        return self._create_user(username, email, password, False, False, **extra_fields)

    def create_superuser(self, username, email, password, **extra_fields):
        user = self._create_user(username, email, password, True, True, **extra_fields)
        user.is_active = True
        user.save(using=self._db)
        return user


class Usuario(AbstractBaseUser,PermissionsMixin):
    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        from clientes.validador import validar_cpf
        errors = {}
        if self.cpf:
            digits = re.sub(r'\D','',self.cpf)
            if len(digits)!=11 or len(set(digits))==1 or not validar_cpf(digits): errors['cpf']='CPF inválido.'
            else: self.cpf=digits
        if self.linhas is None or not 1<=self.linhas<=200: errors['linhas']='Informe de 1 a 200 linhas.'
        if errors: raise ValidationError(errors)

    username = models.CharField(_('username'), max_length=15, unique=True, help_text=_('Required. 15 characters or '
                                                                                       'fewer. Letters, numbers and '
                                                                                       '@/./+/-/_ characters'),
                                validators=[validators.RegexValidator(re.compile(r'^[\w.@+-]+$'),_
                                ('Enter a valid username.'), _('invalid'))])
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=30, blank=True)
    email = models.EmailField(_('email address'), max_length=255, unique=True)
    is_staff = models.BooleanField(_('staff status'), default=False,
                                   help_text=_('Designates whether the user can log into this admin site.'))
    is_active = models.BooleanField(_('active'), default=True,
                                    help_text=_('Designates whether this user should be treated as active. '
                                                'Unselect this instead of deleting accounts.'))
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    cpf = models.CharField(max_length=11, unique=True, blank=True, null=True)
    fone = models.CharField(max_length=14, blank=True, null=True)
    linhas = models.IntegerField(default=50)
    ultimo_mes = models.IntegerField(blank=True, default=1)
    ultimo_ano = models.IntegerField(blank=True, default=2016)
    avatar = models.FileField(upload_to='avatar', max_length=500, null=True)
    uf = models.ForeignKey('clientes.Uf', null=True, blank=True, on_delete=models.PROTECT)

    empresas = models.ManyToManyField('empresa.Empresa')

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'email']

    objects = UserManager()

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def get_full_name(self):
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        return self.first_name


class EsqueceuSenha(models.Model):
    usuario = models.ForeignKey(Usuario,
                                related_name='esqueceusenha',
                                on_delete=models.PROTECT)
    token = models.CharField(max_length=100)
    data = models.DateTimeField()
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return u'%s' % self.usuario.username

    class Meta:
        indexes = [models.Index(fields=['token','ativo'],name='usuario_reset_token_ativo'), models.Index(fields=['usuario','ativo'],name='usuario_reset_user_ativo')]
        verbose_name = _('EsqueceuSenha')
