"""Certificados fiscais privados, fora do diretório público de mídia."""
from pathlib import Path
import uuid
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


def certificate_root():
    return Path(getattr(settings,'PRIVATE_CERTIFICATE_ROOT',Path(settings.BASE_DIR)/'.private'/'certificados')).resolve()


@deconstructible
class PrivateCertificateStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(file_permissions_mode=0o600,directory_permissions_mode=0o700)
    @property
    def base_location(self):return str(certificate_root())
    @property
    def location(self):return str(certificate_root())
    def url(self,name):raise ValueError('Certificados privados não possuem URL pública.')


def certificate_name(instance,filename):return uuid.uuid4().hex+'.pfx'
