from rest_framework.exceptions import PermissionDenied, ValidationError
from .models import Email, Telefone


def permission(user,verb,model):
    if not user.has_perm(f'agenda.{verb}_{model._meta.model_name}'):
        raise PermissionDenied('Sem permissão para '+verb+' registros de '+model._meta.model_name+'.')


def sync_rows(contact,model,rows,user):
    field = 'email' if model is Email else 'fone'
    existing = {obj.pk:obj for obj in model.objects.select_for_update().filter(contato=contact)}
    ids = {row['id'] for row in rows if 'id' in row}
    if not ids.issubset(existing):
        raise ValidationError({field:'Registro de outro contato ou inexistente. Atualize a tela.'})
    for row in rows:
        obj = existing.get(row.get('id'))
        if obj:
            if getattr(obj,field)!=row[field]:
                permission(user,'change',model);setattr(obj,field,row[field]);obj.save(update_fields=[field])
        else:
            permission(user,'add',model);model.objects.create(contato=contact,**{field:row[field]})
    removed = set(existing)-ids
    if removed:
        permission(user,'delete',model);model.objects.filter(pk__in=removed,contato=contact).delete()


def save_contact(serializer,user):
    values = dict(serializer.validated_data)
    children = {model:values.pop(source) for source,model in [('Emails',Email),('Telefones',Telefone)] if source in values}
    old = serializer.instance
    if old:
        for field,value in values.items(): setattr(old,field,value)
        old.clean();old.save();obj=old
    else:
        from .models import Contato
        obj=Contato(**values);obj.clean();obj.save()
    for model,rows in children.items():sync_rows(obj,model,rows,user)
    obj._prefetched_objects_cache={}
    serializer.instance=obj
    return obj
