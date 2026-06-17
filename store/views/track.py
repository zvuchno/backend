"""ViewSet для работы с моделью track."""

from django.db.models import BooleanField, Exists, OuterRef, Value
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from common.permissions import IsArtist, IsStoreObjectOwnerOrReadOnly

from .mixins import ProductActionMixin, SoftDeleteMixin
from store.filters import TrackFilter
from store.models import Favorite, Track
from store.schema import track_schema
from store.serializers import (
    TrackReadDetailSerializer,
    TrackReadSerializer,
    TrackWriteSerializer,
)


@track_schema
class TrackViewSet(ProductActionMixin, SoftDeleteMixin, viewsets.ModelViewSet):
    """API для работы с треками."""

    queryset = Track.objects.all()
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

    def get_permissions(self):
        if self.action == 'create':
            return (IsArtist(),)
        return (IsStoreObjectOwnerOrReadOnly(),)

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return TrackWriteSerializer
        if self.action == 'retrieve':
            return TrackReadDetailSerializer
        return TrackReadSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = (
            super()
            .get_queryset()
            .visible_for(user=user, action=self.action)
            .select_related(
                'album',
                'owner__artist_profile',
                'product',
            )
        )

        if user.is_authenticated:
            favorite_subquery = Favorite.objects.filter(
                user=user,
                product_variant__product=OuterRef('product'),
            )
            queryset = queryset.annotate(
                is_favorite=Exists(favorite_subquery),
            )
        else:
            queryset = queryset.annotate(
                is_favorite=Value(False, output_field=BooleanField()),
            )
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
