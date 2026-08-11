from rest_framework import serializers

from store.constants import (
    DISCOUNT_VALUE_PRECISION,
    MAX_PRICE_DIGITS,
)
from store.models import Report


class ArtistReportSerializer(serializers.ModelSerializer):
    """Финансовый отчет артиста."""

    sales_amount = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=DISCOUNT_VALUE_PRECISION,
    )

    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = (
            'period_start',
            'period_end',
            'sales_amount',
            'file_url',
        )

    def get_file_url(self, obj) -> str:
        request = self.context.get('request')

        if not obj.report_file:
            return None

        url = obj.report_file.url

        if request:
            return request.build_absolute_uri(url)
        return url
