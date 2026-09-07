from rest_framework import serializers
from rest_framework.reverse import reverse

from store.constants import (
    DISCOUNT_VALUE_PRECISION,
    MAX_PRICE_DIGITS,
)
from store.models import Report


class ArtistReportSerializer(serializers.ModelSerializer):
    """Агентский отчет артиста."""

    sales_amount = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=DISCOUNT_VALUE_PRECISION,
    )

    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = (
            'period_start',
            'period_end',
            'sales_amount',
            'download_url',
        )

    def get_download_url(self, obj) -> str | None:
        if not obj.report_file:
            return None

        return reverse(
            'api:store:me-reports-download',
            kwargs={'pk': obj.pk},
            request=self.context.get('request'),
        )
