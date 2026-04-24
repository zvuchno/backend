from django.db.models import QuerySet


class ArtistLegalProfileQuerySet(QuerySet):
    """QuerySet для юридических профилей артистов."""

    def with_user(self):
        """Подтягивает учетную запись."""
        return self.select_related('user')

    def verified(self):
        """Возвращает только подтвержденные юр профили."""
        return self.filter(is_verified=True)


class LegalDataQuerySet(QuerySet):
    """QuerySet для паспортных или банковских данных."""

    def with_legal_profile(self):
        """Подтягивает юр профиль и учетную запись."""
        return self.select_related('legal_profile', 'legal_profile__user')
