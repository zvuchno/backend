"""ViewSet для управления альбомами.

TODO: Пагинация, фильтрация, пермишены.
"""

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .mixins import ProductActionMixin
from store.models import Album
from store.schema import album_schema
from store.serializers import (
    AlbumReadDetailSerializer,
    AlbumReadSerializer,
    AlbumWriteSerializer,
)


@album_schema
class AlbumViewSet(ProductActionMixin, viewsets.ModelViewSet):
    """API для работы с альбомами."""

    permission_classes = (IsAuthenticatedOrReadOnly,)
    http_method_names = ('get', 'post', 'patch', 'delete')

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return AlbumWriteSerializer
        if self.action == 'retrieve':
            return AlbumReadDetailSerializer
        return AlbumReadSerializer

    def get_queryset(self):
        user = self.request.user
        # Админам отдаем всё без фильтров
        if user.is_authenticated and user.is_staff:
            queryset = Album.objects.all()
        else:
            base_filters = Q(is_active=True, is_published=True)
            if self.action == 'list':
                # Общая выдача: только публичные или свои
                visibility_filter = Q(visibility='public')
                if user.is_authenticated:
                    visibility_filter |= Q(owner=user)
                queryset = Album.objects.filter(
                    base_filters & visibility_filter,
                )
            else:
                # Прямой retrieve/update: публичные, по ссылке или свои
                access_filter = Q(visibility__in=['public', 'link_only'])
                if user.is_authenticated:
                    access_filter |= Q(owner=user)
                queryset = Album.objects.filter(base_filters & access_filter)

        if self.action in ('list', 'retrieve'):
            queryset = queryset.select_related('product', 'genre')
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = AlbumReadDetailSerializer(
            instance,
            context=self.get_serializer_context(),
        )
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        read_serializer = AlbumReadDetailSerializer(
            instance,
            context=self.get_serializer_context(),
        )
        return Response(read_serializer.data)
