from rest_framework import serializers

from store.models import Report


class ArtistReportSerializer(serializers.ModelSerializer):
    """Финансовый отчет артиста."""

    report_number = serializers.IntegerField(source='id', read_only=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = (
            'report_number',
            'period_start',
            'period_end',
            'items_count',
            'gross_amount',
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
