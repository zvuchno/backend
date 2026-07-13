from rest_framework import serializers


class CdekCalculateSerializer(serializers.Serializer):
    """Сериализатор входных данных для расчёта стоимости доставки СДЭК."""

    tariffs = serializers.ChoiceField(
        choices=[
            ('office', 'Самовывоз из ПВЗ'),
            ('door', 'Курьер (до двери)'),
            ('pickup', 'Постомат'),
        ],
        required=True,
        help_text=(
            'Тип доставки: office (до ПВЗ), door (до двери), pickup (постомат)'
        ),
    )
    city_code = serializers.IntegerField(
        required=True,
        help_text='Код города выдачи заказа от СДЭК',
    )
