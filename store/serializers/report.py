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
            'id',
            'period_start',
            'period_end',
            'items_count',
            'sales_amount',
            'file_url',
            'created_at',
        )

    def get_file_url(self, obj):
        request = self.context.get('request')

        if not obj.report_file:
            return None

        url = obj.report_file.url

        if request:
            return request.build_absolute_uri(url)
        return url


class ArtistDetailReportSerializer(ArtistReportSerializer):
    """Детальный финансовый отчет артиста."""

    donation_amount = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=DISCOUNT_VALUE_PRECISION,
    )
    discount_amount = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=DISCOUNT_VALUE_PRECISION,
    )
    delivery_amount = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=DISCOUNT_VALUE_PRECISION,
    )
    commission_amount = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=DISCOUNT_VALUE_PRECISION,
    )
    payout_amount = serializers.DecimalField(
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=DISCOUNT_VALUE_PRECISION,
    )

    class Meta(ArtistReportSerializer.Meta):
        fields = ArtistReportSerializer.Meta.fields + (
            'period_type',
            'status',
            'orders_count',
            'donation_amount',
            'discount_amount',
            'delivery_amount',
            'commission_amount',
            'payout_amount',
        )
