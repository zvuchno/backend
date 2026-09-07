"""Представления юридических документов."""

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from users.consents_policy import ConsentPolicy
from users.models import ConsentDocument
from users.schemas import consent_doc_schema
from users.schemas.consent_documents import CONSENT_DOC_TAGS
from users.serializers import (
    ConsentDocumentDetailSerializer,
    ConsentDocumentSerializer,
    ConsentRequirementSerializer,
)


@consent_doc_schema
class ConsentDocumentViewSet(viewsets.ReadOnlyModelViewSet):
    """Представление для отображения юридических документов."""

    queryset = ConsentDocument.objects.filter(is_active=True)
    permission_classes = (AllowAny,)
    lookup_field = 'document_type'
    pagination_class = None

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ConsentDocumentDetailSerializer
        return ConsentDocumentSerializer


class ConsentRequirementsView(APIView):
    """Возвращает требования согласий для пользовательских сценариев."""

    permission_classes = (AllowAny,)

    @extend_schema(
        tags=CONSENT_DOC_TAGS,
        responses=ConsentRequirementSerializer(many=True),
    )
    def get(self, request):
        return Response(ConsentPolicy.get_requirements())
