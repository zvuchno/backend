"""Фабрики тестовых пользователей и профилей."""

import factory
from django.contrib.auth import get_user_model

from users.models import ArtistProfile, ListenerProfile

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
    password = factory.PostGenerationMethodCall('set_password', 'password')


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

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f'Артист {n}')
    city = 'Москва'
    description = 'Тестовое описание артиста.'
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
