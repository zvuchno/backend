from pathlib import Path

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.viewsets import GenericViewSet

from common.permissions import IsArtistOrLabel

from store.filters.report import ArtistReportFilter
from store.models import Report
from store.schema import artist_reports_schema
from store.serializers.report import ArtistReportSerializer


@artist_reports_schema
class ArtistReportViewSet(
    mixins.ListModelMixin,
    GenericViewSet,
):
    """Агентские отчеты текущего получателя выплаты."""

    queryset = Report.objects.all()
    serializer_class = ArtistReportSerializer
    permission_classes = (IsArtistOrLabel,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ArtistReportFilter

    def get_queryset(self):
        return Report.objects.filter(
            payout_recipient=self.request.user,
            status=Report.Status.READY,
        ).order_by('-period_end')

    @action(
        detail=True,
        methods=('get',),
        url_path='download',
        url_name='download',
    )
    def download(self, request, pk: int):
        """Скачивает PDF-файл агентского отчета."""
        report = get_object_or_404(
            self.get_queryset(),
            pk=pk,
        )

        if not report.report_file:
            raise Http404('Файл отчета отсутствует.')

        filename = Path(report.report_file.name).name

        response = FileResponse(
            report.report_file.open('rb'),
            content_type='application/pdf',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response
