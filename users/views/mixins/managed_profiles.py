from django.http import Http404

from common.access import managed_artist_q

from users.models import ArtistProfile


class ManagedArtistProfileMixin:
    """Миксин для получения доступного управляемого профиля."""

    profile_url_kwarg = 'profile_id'
    select_related = ()
    prefetch_related = ()

    def get_artist_queryset(self):
        """Возвращает queryset доступных пользователю профилей."""
        queryset = ArtistProfile.objects.filter(
            managed_artist_q(
                self.request.user,
                prefix='',
            ),
            is_active=True,
        )

        if self.select_related:
            queryset = queryset.select_related(*self.select_related)

        if self.prefetch_related:
            queryset = queryset.prefetch_related(*self.prefetch_related)

        return queryset

    def get_artist_profile(self):
        """Возвращает доступный профиль из параметров URL."""
        try:
            return self.get_artist_queryset().get(
                pk=self.kwargs[self.profile_url_kwarg],
            )
        except ArtistProfile.DoesNotExist:
            raise Http404('Профиль артиста не найден.')
