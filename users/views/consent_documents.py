"""Представления юридических документов."""

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from users.models import ConsentDocument
from users.schemas import consent_doc_schema
from users.serializers import (
    ConsentDocumentDetailSerializer,
    ConsentDocumentSerializer,
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
