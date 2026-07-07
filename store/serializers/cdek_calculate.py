from rest_framework import serializers


class CdekCalculateSerializer(serializers.Serializer):
    """Сериализатор входных данных для расчёта стоимости доставки СДЭК."""

    delivery_type = serializers.ChoiceField(
        choices=[
            ('offices', 'Самовывоз из ПВЗ'),
            ('door', 'Курьер (до двери)'),
        ],
        required=True,
        help_text='Тип доставки: offices (до ПВЗ) или door (до двери)',
    )
    city_code = serializers.IntegerField(
        required=True,
        help_text='Код города выдачи заказа от СДЭК',
    )
