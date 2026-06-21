from django.db.models import QuerySet
from rest_framework.generics import get_object_or_404

from store.models import ListenerAlbumAccess, ListenerTrackAccess


class PurchasedMusicAccessMixin:
    """Помощники для получения объектов, доступных текущему слушателю."""

    @staticmethod
    def get_album_access_queryset() -> QuerySet[ListenerAlbumAccess]:
        """Возвращает queryset доступов к альбомам с данными релиза."""
        return ListenerAlbumAccess.objects.select_related(
            'album',
            'album__owner',
            'album__owner__artist_profile',
        )

    @staticmethod
    def get_track_access_queryset() -> QuerySet[ListenerTrackAccess]:
        """Возвращает queryset доступов к трекам с данными релиза."""
        return ListenerTrackAccess.objects.select_related(
            'track',
            'track__album',
            'track__album__owner',
            'track__album__owner__artist_profile',
        )

    def get_album_access_or_404(
        self,
        *,
        user,
        album_id: int,
        require_full_access: bool = False,
    ) -> ListenerAlbumAccess:
        """Возвращает доступ пользователя к альбому или 404."""
        filters = {
            'user': user,
            'album_id': album_id,
        }

        if require_full_access:
            filters['is_fully_available'] = True

        return get_object_or_404(
            self.get_album_access_queryset(),
            **filters,
        )

    def get_track_access_or_404(
        self,
        *,
        user,
        track_id: int,
    ) -> ListenerTrackAccess:
        """Возвращает доступ пользователя к треку или 404."""
        return get_object_or_404(
            self.get_track_access_queryset(),
            user=user,
            track_id=track_id,
        )
