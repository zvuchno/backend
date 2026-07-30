from django.http import Http404

from users.models import ArtistProfile


class ArtistProfileQuerysetMixin:
    """Миксин настройки queryset профилей артистов."""

    select_related = ()
    prefetch_related = ()

    def get_artist_queryset(self):
        """Возвращает настроенный queryset профилей."""
        queryset = ArtistProfile.objects.all()

        if self.select_related:
            queryset = queryset.select_related(*self.select_related)

        if self.prefetch_related:
            queryset = queryset.prefetch_related(*self.prefetch_related)

        return queryset


class CurrentArtistProfileMixin(ArtistProfileQuerysetMixin):
    """Миксин для получения профиля текущего артиста."""

    def get_artist_profile(self):
        try:
            return self.get_artist_queryset().get(user=self.request.user)
        except ArtistProfile.DoesNotExist:
            raise Http404('Профиль артиста не найден.')
