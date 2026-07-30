from django.http import Http404

from common.access import managed_artist_q

from users.models import ArtistProfile
from users.views.mixins.artist_profile import ArtistProfileQuerysetMixin


class ManagedArtistProfileMixin(ArtistProfileQuerysetMixin):
    """Миксин для получения доступного управляемого профиля."""

    profile_url_kwarg = 'profile_id'

    def get_artist_queryset(self):
        return (
            super()
            .get_artist_queryset()
            .filter(
                managed_artist_q(
                    self.request.user,
                    prefix='',
                ),
                is_active=True,
            )
        )

    def get_artist_profile(self):
        """Возвращает доступный профиль из параметров URL."""
        try:
            return self.get_artist_queryset().get(
                pk=self.kwargs[self.profile_url_kwarg],
            )
        except ArtistProfile.DoesNotExist:
            raise Http404('Профиль артиста не найден.')
