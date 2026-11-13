from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm,AdminUserCreationForm
from .models import Usuario,EsqueceuSenha


class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model=Usuario
        fields='__all__'


class UsuarioCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model=Usuario
        fields=('username','first_name','last_name','email')


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form=UsuarioChangeForm
    add_form=UsuarioCreationForm
    fieldsets=UserAdmin.fieldsets+(("Perfil e empresas",{'fields':('cpf','fone','linhas','avatar','uf','empresas')}),)
    add_fieldsets=((None,{'classes':('wide',),'fields':('username','first_name','last_name','email','usable_password','password1','password2')}),)
    filter_horizontal=('groups','user_permissions','empresas')
    def has_add_permission(self,request):return request.user.is_superuser
    def has_change_permission(self,request,obj=None):return request.user.is_superuser
    def has_delete_permission(self,request,obj=None):return request.user.is_superuser
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(pk=request.user.pk)
    def get_readonly_fields(self,request,obj=None):
        if request.user.is_superuser:return super().get_readonly_fields(request,obj)
        return tuple(field.name for field in Usuario._meta.fields)+('groups','user_permissions','empresas')


@admin.register(EsqueceuSenha)
class RecuperacaoAdmin(admin.ModelAdmin):
    exclude=('token',)
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
    def get_queryset(self,request):
        qs=super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(usuario=request.user)
