"""ViewSet для работы с моделью track."""

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .mixins import ProductActionMixin
from store.filters import TrackFilter
from store.models import Track
from store.schema import track_schema
from store.serializers import (
    TrackReadDetailSerializer,
    TrackReadSerializer,
    TrackWriteSerializer,
)


@track_schema
class TrackViewSet(ProductActionMixin, viewsets.ModelViewSet):
    """API для работы с треками."""

    queryset = Track.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)
    http_method_names = ('get', 'post', 'patch', 'delete')
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    )

    filterset_class = TrackFilter
    search_fields = ('name',)
    ordering_fields = ('name', 'position')
    ordering = ('album', 'position')

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return TrackWriteSerializer
        if self.action == 'retrieve':
            return TrackReadDetailSerializer
        return TrackReadSerializer

    def get_queryset(self):
        user = self.request.user

        # Админам отдаем всё без фильтров
        if user.is_authenticated and user.is_staff:
            queryset = Track.objects.all()
        else:
            # Базовый фильтр: активные
            filters = Q(is_active=True)
            # Если юзер залогинен, добавляем к фильтру 'или это моё'
            if user.is_authenticated:
                filters |= Q(owner=user)
            queryset = Track.objects.filter(filters)

        if self.action in ('list', 'retrieve'):
            queryset = queryset.select_related('product')

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = TrackReadDetailSerializer(
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
        read_serializer = TrackReadDetailSerializer(
            instance,
            context=self.get_serializer_context(),
        )
        return Response(read_serializer.data)
