from django.db.models import BooleanField, Exists, OuterRef, Value

from store.models import Favorite, Track


class TrackReadQuerysetMixin:
    """Подготавливает queryset треков для read-контрактов API."""

    def get_track_read_queryset(
        self,
        *,
        action: str,
        queryset=None,
    ):
        """Возвращает доступные треки с данными read-контракта."""
        user = self.request.user

        if queryset is None:
            queryset = Track.objects.all()

        queryset = queryset.visible_for(
            user=user,
            action=action,
        ).select_related(
            'album',
            'owner__artist_profile',
            'product',
        )

        if user.is_authenticated:
            favorite_subquery = Favorite.objects.filter(
                user=user,
                product_variant__product=OuterRef('product'),
            )
            return queryset.annotate(
                is_favorite=Exists(favorite_subquery),
            )

        return queryset.annotate(
            is_favorite=Value(
                False,
                output_field=BooleanField(),
            ),
        )
