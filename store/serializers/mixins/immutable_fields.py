from rest_framework import serializers


class ImmutableFieldsSerializerMixin:
    """Запрещает изменение указанных полей после создания объекта."""

    immutable_fields = ()

    def validate(self, attrs):
        """Проверяет неизменность защищённых полей."""
        attrs = super().validate(attrs)

        if self.instance is None:
            return attrs

        errors = {}

        for field_name in self.immutable_fields:
            if field_name not in attrs:
                continue

            id_field_name = f'{field_name}_id'

            if hasattr(self.instance, id_field_name):
                current_value = getattr(
                    self.instance,
                    id_field_name,
                )
            else:
                current_value = getattr(
                    self.instance,
                    field_name,
                )

            new_value = attrs[field_name]
            new_value = getattr(new_value, 'pk', new_value)

            if current_value != new_value:
                errors[field_name] = 'Это поле нельзя изменить после создания.'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
