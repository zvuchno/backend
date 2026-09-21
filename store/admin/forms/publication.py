class PublicationRecipientFormMixin:
    """Проверяет наличие получателя выплат при публикации."""

    def clean(self):
        cleaned_data = super().clean()

        if (
            cleaned_data.get('is_published') is not True
            or self.instance.payout_recipient_id is not None
        ):
            return cleaned_data

        artist = cleaned_data.get('artist')

        if artist is None and self.instance.artist_id is not None:
            artist = self.instance.artist

        if artist is not None and artist.default_payout_recipient is None:
            self.add_error(
                'is_published',
                'Нельзя опубликовать контент без получателя выплат.',
            )

        return cleaned_data
