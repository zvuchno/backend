import pytest
from django.db import IntegrityError, transaction

from config import settings
from store.models import Album, Merch
from store.tests.factories import AlbumFactory, MerchFactory
from users.models import ArtistProfile


@pytest.mark.django_db
def test_unclaimed_artist_can_have_draft_content():
    """Неподключённый артист может иметь черновики без получателя выплат."""
    artist = ArtistProfile.objects.create(
        name='Импортированный артист',
    )

    album = Album.objects.create(
        artist=artist,
        name='Импортированный альбом',
    )

    merch = Merch.objects.create(
        artist=artist,
        name='Импортированный мерч',
    )

    album.refresh_from_db()
    merch.refresh_from_db()

    assert artist.default_payout_recipient is None

    for content in (album, merch):
        assert content.artist == artist
        assert content.created_by is None
        assert content.payout_recipient is None
        assert content.is_published is False


@pytest.mark.django_db
@pytest.mark.parametrize('factory', [AlbumFactory, MerchFactory])
def test_database_rejects_publication_without_payout_recipient(
    factory,
    monkeypatch,
):
    """База запрещает публикацию без получателя выплат."""
    if 'silk' in settings.INSTALLED_APPS:
        monkeypatch.setattr(
            'silk.sql._should_wrap',
            lambda _query: False,
        )
    content = factory(
        is_published=False,
        payout_recipient=None,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            type(content).objects.filter(pk=content.pk).update(
                is_published=True,
            )

    content.refresh_from_db()

    assert content.is_published is False
    assert content.payout_recipient_id is None
