from rest_framework import serializers


class CdekCalculateSerializer(serializers.Serializer):
    """Сериализатор входящего кода ПВЗ."""

    delivery_type = serializers.ChoiceField(
        choices=[('pickpoint', 'Самовывоз из ПВЗ'), ('courier', 'Курьер')],
        required=True,
        help_text='Тип доставки: pickpoint (до ПВЗ) или courier (до двери)',
    )
    city_code = serializers.IntegerField(
        required=True,
        help_text='Код пункта выдачи заказа (ПВЗ) от СДЭК',
    )
