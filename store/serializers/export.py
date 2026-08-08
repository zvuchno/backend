from datetime import timedelta

from rest_framework import serializers

from store.constants import MAX_SALES_EXPORT_PERIOD_DAYS


class SalesExportQuerySerializer(serializers.Serializer):
    """Параметры выгрузки отчета продаж."""

    period_start = serializers.DateField(
        required=True,
        help_text='Начало периода.',
    )
    period_end = serializers.DateField(
        required=True,
        help_text='Конец периода.',
    )

    def validate(self, attrs):
        period_start = attrs['period_start']
        period_end = attrs['period_end']

        if period_start > period_end:
            raise serializers.ValidationError(
                'Дата начала периода не может быть позже даты окончания.',
            )

        if period_end - period_start > timedelta(
            days=MAX_SALES_EXPORT_PERIOD_DAYS,
        ):
            raise serializers.ValidationError(
                'Максимальный период выгрузки — '
                f'{MAX_SALES_EXPORT_PERIOD_DAYS} дней.',
            )

        return attrs
