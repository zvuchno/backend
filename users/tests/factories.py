"""Фабрики тестовых пользователей и профилей."""

from datetime import timedelta, timezone

import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from factory import LazyFunction, SubFactory
from factory.django import DjangoModelFactory

from users.models import (
    ArtistProfile,
    ArtistProfileClaimInvitation,
    ListenerProfile,
    TokenInvitation,
    TokenInvitationStatus,
)
from users.models.artist import ArtistProfileType
from users.services.invitation import hash_invitation_token

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Фабрика пользователя."""

    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f'user{n}@test.local')
    username = factory.Sequence(lambda n: f'user{n}')
    phone = factory.Sequence(lambda n: f'+7999000{n:04d}')
    is_active = True
    is_email_verified = True
    is_phone_verified = False
    password = factory.LazyFunction(lambda: make_password('password'))


class ListenerProfileFactory(factory.django.DjangoModelFactory):
    """Фабрика профиля слушателя."""

    class Meta:
        model = ListenerProfile

    user = factory.SubFactory(UserFactory)
    full_name = factory.Sequence(lambda n: f'Слушатель {n}')
    is_active = True


class ArtistProfileFactory(factory.django.DjangoModelFactory):
    """Фабрика профиля артиста."""

    class Meta:
        model = ArtistProfile

    profile_type = ArtistProfileType.ARTIST
    user = factory.SubFactory(UserFactory)
    label = None
    name = factory.Sequence(lambda n: f'Артист {n}')
    city = 'Москва'
    description = 'Тестовое описание артиста.'
    is_active = True


class LabelProfileFactory(factory.django.DjangoModelFactory):
    """Фабрика публичного профиля лейбла."""

    class Meta:
        model = ArtistProfile

    profile_type = ArtistProfileType.LABEL
    user = factory.SubFactory(UserFactory)
    label = None
    name = factory.Sequence(lambda n: f'Лейбл {n}')
    city = 'Москва'
    description = 'Тестовое описание лейбла.'
    is_active = True


class ListenerUserFactory(UserFactory):
    """Фабрика пользователя с профилем слушателя."""

    listener_profile = factory.RelatedFactory(
        ListenerProfileFactory,
        factory_related_name='user',
    )


class ArtistUserFactory(UserFactory):
    """Фабрика пользователя с профилями слушателя и артиста."""

    listener_profile = factory.RelatedFactory(
        ListenerProfileFactory,
        factory_related_name='user',
    )
    artist_profile = factory.RelatedFactory(
        ArtistProfileFactory,
        factory_related_name='user',
    )


class LabelUserFactory(UserFactory):
    """Фабрика пользователя с профилями слушателя и лейбла."""

    listener_profile = factory.RelatedFactory(
        ListenerProfileFactory,
        factory_related_name='user',
    )
    artist_profile = factory.RelatedFactory(
        LabelProfileFactory,
        factory_related_name='user',
    )


class TokenInvitationFactory(DjangoModelFactory):
    """Фабрика токен-инвайта."""

    class Meta:
        model = TokenInvitation

    recipient_email = factory.Sequence(
        lambda n: f'invited{n}@test.local',
    )
    token_hash = factory.Sequence(
        lambda n: hash_invitation_token(f'test-token-{n}'),
    )
    status = TokenInvitationStatus.PENDING
    created_by = SubFactory(LabelUserFactory)
    expires_at = LazyFunction(
        lambda: timezone.now() + timedelta(days=7),
    )


class ArtistProfileClaimInvitationFactory(DjangoModelFactory):
    """Фабрика приглашения к управлению профилем артиста."""

    class Meta:
        model = ArtistProfileClaimInvitation

    invitation = SubFactory(TokenInvitationFactory)
    artist = SubFactory(
        ArtistProfileFactory,
        user=None,
    )
