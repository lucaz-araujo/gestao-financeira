from copy import copy
from decimal import Decimal

from django.core.exceptions import ValidationError as ModelValidationError
from rest_framework import serializers
from .models import Produto


class ProdutoSerializer(serializers.ModelSerializer):
    valor = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))

    class Meta:
        model = Produto
        fields = ('id', 'empresa', 'descricao', 'sigla', 'tipo_produto', 'valor')
        read_only_fields = ('id', 'empresa')
        extra_kwargs = {
            'sigla': {'required': True, 'allow_null': False, 'allow_blank': False},
        }

    def validate(self, attrs):
        candidate = copy(self.instance) if self.instance else Produto()
        for name, value in attrs.items():
            setattr(candidate, name, value)
        try:
            candidate.clean()
        except ModelValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs
