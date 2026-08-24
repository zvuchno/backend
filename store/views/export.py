from rest_framework.views import APIView

from common.permissions import IsArtistOrLabel

from store.schema import sales_export_schema
from store.serializers.export import SalesExportQuerySerializer
from store.services.export import SalesExportService


@sales_export_schema
class SalesExportView(APIView):
    """Экспорт детализированного отчета по продажам в CSV."""

    permission_classes = (IsArtistOrLabel,)

    def get(self, request):
        """Возвращает CSV-файл с доступными пользователю продажами."""
        serializer = SalesExportQuerySerializer(
            data=request.query_params,
        )
        serializer.is_valid(raise_exception=True)

        return SalesExportService.build_response(
            user=request.user,
            **serializer.validated_data,
        )
