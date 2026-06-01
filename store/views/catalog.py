from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from store.filters import ProductCatalogFilter
from store.models import Album, Favorite, Merch, Product, ProductVariant
from store.schema import catalog_list_schema
from store.serializers import CatalogCardSerializer
from store.serializers.catalog_detail import (
    CatalogMerchDetailSerializer,
    CatalogReleaseDetailSerializer,
)


@catalog_list_schema
class ProductCatalogListView(ListAPIView):
    """Список товаров каталога."""

    serializer_class = CatalogCardSerializer
    permission_classes = (AllowAny,)
    filter_backends = (
        DjangoFilterBackend,
        filters.SearchFilter,
    )
    filterset_class = ProductCatalogFilter
    search_fields = (
        'album__name',
        'merch__name',
        'album__owner__artist_profile__name',
        'merch__owner__artist_profile__name',
    )

    def get_queryset(self):
        """Возвращает товары каталога."""
        catalog_type = self.request.query_params.get('type')
        kind = self.request.query_params.get('kind')
        if kind:
            return Product.objects.for_merch_cards()
        return Product.objects.for_catalog_type(catalog_type)

    def get_serializer_context(self):
        """Возвращает контекст сериализатора."""
        context = super().get_serializer_context()
        user = self.request.user

        if user.is_authenticated:
            context['favorite_product_ids'] = set(
                Favorite.objects.filter(
                    user=user,
                ).values_list(
                    'product_variant__product_id',
                    flat=True,
                ),
            )
        else:
            context['favorite_product_ids'] = set()

        return context


class CatalogReleaseDetailView(RetrieveAPIView):
    """Витринная detail-карточка релиза."""

    serializer_class = CatalogReleaseDetailSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        """Возвращает публичные релизы с вариантами покупки."""
        digital_active_variants = (
            ProductVariant.objects
            .filter(is_active=True)
            .select_related(
                'product',
                'product__album',
            )
            .order_by('id')
        )

        carrier_active_variants = (
            ProductVariant.objects
            .filter(is_active=True)
            .select_related(
                'product',
                'product__merch',
                'product__merch__kind',
                'product__merch__album',
            )
            .order_by('id')
        )

        carrier_qs = (
            Merch.objects
            .filter(
                kind__is_carrier=True,
                is_active=True,
                is_published=True,
                visibility=Merch.Visibility.PUBLIC,
            )
            .select_related(
                'album',
                'kind',
                'product',
            )
            .prefetch_related(
                'images_merch',
                Prefetch(
                    'product__variants',
                    queryset=carrier_active_variants,
                    to_attr='active_carriers_variants',
                ),
            )
            .order_by('id')
        )

        return (
            Album.objects
            .filter(
                is_published=True,
                visibility=Album.Visibility.PUBLIC,
            )
            .select_related(
                'product',
                'genre',
                'owner__artist_profile',
            )
            .prefetch_related(
                Prefetch(
                    'product__variants',
                    queryset=digital_active_variants,
                    to_attr='active_digital_variants',
                ),
                Prefetch(
                    'merch',
                    queryset=carrier_qs,
                    to_attr='active_carriers',
                ),
            )
        )


class CatalogMerchDetailView(RetrieveAPIView):
    """Витринная detail-карточка обычного мерча."""

    serializer_class = CatalogMerchDetailSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        """Возвращает публичный обычный мерч с вариантами покупки."""
        active_variants = (
            ProductVariant.objects
            .filter(is_active=True)
            .select_related('product')
            .order_by('id')
        )

        return (
            Merch.objects
            .filter(
                kind__is_carrier=False,
                is_published=True,
                visibility=Merch.Visibility.PUBLIC,
            )
            .select_related(
                'product',
                'kind',
                'owner__artist_profile',
            )
            .prefetch_related(
                'images_merch',
                Prefetch(
                    'product__variants',
                    queryset=active_variants,
                    to_attr='active_variants',
                ),
            )
        )
