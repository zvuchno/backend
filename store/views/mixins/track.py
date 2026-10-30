from django.db.models import BooleanField, Exists, OuterRef, Value

from store.models import Favorite, ListenerTrackAccess, ReleaseTrack


class TrackReadQuerysetMixin:
    """Подготавливает queryset треков для read-контрактов API."""

    def get_track_read_queryset(
        self,
        *,
        action: str,
        queryset=None,
        player_preview: bool | None = None,
    ):
        """Возвращает доступные треки с данными read-контракта."""
        user = self.request.user

        if queryset is None:
            queryset = ReleaseTrack.objects.all()

        if player_preview is None:
            queryset = queryset.visible_for(
                user=user,
                action=action,
            )
        else:
            queryset = queryset.for_player(
                user,
                preview=player_preview,
            )

            if user.is_authenticated:
                accessible_track_ids = ListenerTrackAccess.objects.filter(
                    user=user,
                ).values('track_id')

                queryset = queryset | ReleaseTrack.objects.filter(
                    pk__in=accessible_track_ids,
                )

        queryset = queryset.select_related(
            'release',
            'release__artist',
            'recording',
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
