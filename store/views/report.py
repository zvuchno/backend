from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from common.permissions import IsArtistOrLabel

from store.filters import ArtistReportFilter
from store.models import Report
from store.schema import artist_reports_schema
from store.serializers import ArtistReportSerializer


@artist_reports_schema
class ArtistReportViewSet(
    mixins.ListModelMixin,
    GenericViewSet,
):
    """Финансовые отчеты текущего артиста."""

    queryset = Report.objects.all()
    serializer_class = ArtistReportSerializer
    permission_classes = (IsArtistOrLabel,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ArtistReportFilter

    def get_queryset(self):
        return (
            Report.objects
            .filter(
                artist__user=self.request.user,
                status=Report.Status.READY,
            )
            .select_related('artist')
            .order_by('-period_end')
        )
