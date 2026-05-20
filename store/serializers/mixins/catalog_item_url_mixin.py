from django.urls import reverse


class CatalogTargetURLMixin:
    """Миксин для формирования ссылок каталожных карточек."""

    def get_album_target_url(self, album) -> str:
        """Возвращает ссылку на карточку альбома."""
        return reverse(
            'api:store:albums-detail',
            kwargs={'pk': album.pk},
        )

    def get_album_target_url_by_id(self, album_id: int) -> str:
        """Возвращает ссылку на карточку альбома по id."""
        return reverse(
            'api:store:albums-detail',
            kwargs={'pk': album_id},
        )

    def get_merch_target_url(self, merch) -> str:
        """Возвращает ссылку на карточку мерча."""
        # return reverse(
        #     'api:store:merch-detail',
        #     kwargs={'pk': merch.pk},
        # )
        return reverse(
            f'/api/v1/store/merch/{merch.pk}/',
        )

    def get_artist_url(self, artist_profile) -> str:
        return reverse(
            'api:users:artist_public',
            kwargs={'slug': artist_profile.slug},
        )
