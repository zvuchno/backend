"""ViewSet для управления альбомами.

Предоставляет полный цикл CRUD-операций для модели Album.
TODO: Пагинация, фильтрация, пермишены.
"""

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from store.models import Album
from store.schema import album_schema
from store.serializers import (
    AlbumReadDetailSerializer,
    AlbumReadSerializer,
    AlbumWriteSerializer,
)


@album_schema
class AlbumViewSet(viewsets.ModelViewSet):
    """API для работы с альбомами."""

    permission_classes = (IsAuthenticatedOrReadOnly,)

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return AlbumWriteSerializer
        if self.action == 'retrieve':
            return AlbumReadDetailSerializer
        return AlbumReadSerializer

    def get_queryset(self):
        user = self.request.user

        # Если это администратор — отдаем всё
        if user.is_authenticated and user.is_staff:
            queryset = Album.objects.all()
        else:
            # Базовый фильтр: активные, опубликованные и со статусом public
            filters = Q(is_active=True, is_published=True, visibility='public')
            # Если юзер залогинен, добавляем к фильтру 'или это мой альбом'
            if user.is_authenticated:
                filters |= Q(owner=user)
            queryset = Album.objects.filter(filters)

        # Оптимизация (N+1 problem)
        if self.action == 'list':
            # Для списка подтягиваем основную карточку продукта
            return queryset.select_related('product', 'genre')
        if self.action == 'retrieve':
            # Для деталки тянем всё дерево связей:
            # Альбом -> Продукт -> Варианты -> Носитель
            return queryset.select_related(
                'product',
                'genre',
            ).prefetch_related('product__variants__carrier')
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance

        # Используем другой сериализатор для ответа
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
        instance = serializer.save()
        read_serializer = AlbumReadDetailSerializer(
            instance,
            context=self.get_serializer_context(),
        )
        return Response(read_serializer.data)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
