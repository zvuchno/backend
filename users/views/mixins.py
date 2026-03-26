"""Миксины для представлений пользователей."""

from django.http import Http404

from users.models import ArtistProfile


class CurrentArtistProfileMixin:
    """Миксин для получения профиля текущего артиста."""

    select_related = ()
    prefetch_related = ()

    def get_artist_queryset(self):
        queryset = ArtistProfile.objects.all()

        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        if self.prefetch_related:
            queryset = queryset.prefetch_related(*self.prefetch_related)

        return queryset

    def get_artist_profile(self):
        try:
            return self.get_artist_queryset().get(user=self.request.user)
        except ArtistProfile.DoesNotExist:
            raise Http404('Профиль артиста не найден.')
