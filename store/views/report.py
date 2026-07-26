from rest_framework.viewsets import ReadOnlyModelViewSet

from common.permissions import IsArtistOrLabel

from store.models import Report
from store.schema import artist_reports_schema
from store.serializers.report import ArtistReportSerializer


@artist_reports_schema
class ArtistReportViewSet(ReadOnlyModelViewSet):
    """Финансовые отчеты текущего артиста."""

    serializer_class = ArtistReportSerializer
    permission_classes = (IsArtistOrLabel,)

    def get_queryset(self):
        return Report.objects.filter(
            artist__user=self.request.user,
            status=Report.Status.READY,
        ).order_by('-period_end')
