from rest_framework.views import APIView

from common.permissions import IsArtistOrLabel

from store.schema import sales_export_schema
from store.serializers.export import SalesExportQuerySerializer
from store.services.export import SalesExportService


@sales_export_schema
class SalesExportView(APIView):
    """Экспорт детализированного отчета по продажам артиста в CSV."""

    permission_classes = (IsArtistOrLabel,)

    def get(self, request):
        """Возвращает CSV-файл с продажами артиста за период."""
        serializer = SalesExportQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)

        artist = request.user.artist_profile

        return SalesExportService.build_response(
            artist=artist,
            **serializer.validated_data,
        )
