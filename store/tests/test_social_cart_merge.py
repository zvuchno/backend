"""Тесты объединения корзины после социальной аутентификации."""

from unittest.mock import patch

import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from allauth.socialaccount.providers.vk.views import VKOAuth2Adapter
from allauth.socialaccount.providers.yandex.views import YandexOAuth2Adapter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.contrib.sites.models import Site
from django.urls import reverse
from rest_framework import status

from store.models import Cart, CartItem
from store.services.cart_service import CartService
from users.consents_policy import ConsentPolicy, ConsentScenario
from users.models import ConsentDocument
from users.views import VKLogin, YandexLogin

User = get_user_model()

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.usefixtures('publication_readiness_disabled'),
]


SOCIAL_PROVIDERS = {
    'vk': (VKOAuth2Adapter, 'api:users:vk_login'),
    'yandex': (YandexOAuth2Adapter, 'api:users:yandex_login'),
}


@pytest.fixture(autouse=True)
def disable_social_auth_throttling(monkeypatch):
    """Не связывает интеграционные тесты с общим throttle cache."""
    monkeypatch.setattr(VKLogin, 'throttle_classes', [])
    monkeypatch.setattr(YandexLogin, 'throttle_classes', [])


@pytest.fixture
def listener_registration_consents():
    """Создаёт обязательные согласия регистрации слушателя."""
    document_types = ConsentPolicy.get_required(
        ConsentScenario.LISTENER_REGISTRATION,
    )
    for document_type in document_types:
        ConsentDocument.objects.create(
            document_type=document_type,
            version='1.0',
            content=f'Тестовый документ: {document_type}',
            is_active=True,
        )
    return list(document_types)


def configure_social_provider(monkeypatch, provider, uid, email):
    """Подменяет только внешний ответ OAuth-провайдера."""
    adapter_class, url_name = SOCIAL_PROVIDERS[provider]

    app = SocialApp.objects.create(
        provider=provider,
        name=f'Test {provider}',
        client_id=f'{provider}-client-id',
        secret=f'{provider}-secret',
    )
    app.sites.add(Site.objects.get(pk=settings.SITE_ID))

    def complete_login(
        adapter,
        request,
        social_app,
        token,
        **kwargs,
    ) -> SocialLogin:
        account = SocialAccount(
            provider=provider,
            uid=uid,
            extra_data={
                'email': email,
                'client_id': social_app.client_id,
            },
        )
        social_user = User(
            email=email,
            username=email.split('@')[0],
        )
        email_address = EmailAddress(
            email=email,
            verified=True,
            primary=True,
        )
        return SocialLogin(
            user=social_user,
            account=account,
            email_addresses=[email_address],
            provider=adapter.get_provider(),
        )

    monkeypatch.setattr(adapter_class, 'complete_login', complete_login)
    return reverse(url_name)


def create_guest_cart(api_client, cart_add_url, variant):
    """Создаёт гостевую корзину и возвращает её исходный ключ сессии."""
    response = api_client.post(
        cart_add_url,
        data={'product_variant': variant.id, 'quantity': 2},
        format='json',
    )
    assert response.status_code == status.HTTP_201_CREATED
    return api_client.cookies[settings.SESSION_COOKIE_NAME].value


@pytest.mark.parametrize('provider', ['vk', 'yandex'])
def test_social_login_merges_cart_after_session_cycle_key(
    api_client,
    cart_add_url,
    monkeypatch,
    provider,
    user_factory,
    variant_factory,
):
    """VK и Яндекс объединяют корзину по ключу до cycle_key()."""
    user = user_factory(
        email=f'{provider}.listener@example.test',
        username=f'{provider}_listener',
    )
    uid = f'{provider}-existing-uid'
    SocialAccount.objects.create(user=user, provider=provider, uid=uid)
    social_url = configure_social_provider(
        monkeypatch,
        provider,
        uid,
        user.email,
    )
    variant = variant_factory(product_type='merch')
    guest_session_key = create_guest_cart(
        api_client,
        cart_add_url,
        variant,
    )
    cycle_key_calls = []
    original_cycle_key = SessionStore.cycle_key

    def track_cycle_key(session) -> None:
        cycle_key_calls.append(session.session_key)
        original_cycle_key(session)

    monkeypatch.setattr(SessionStore, 'cycle_key', track_cycle_key)

    response = api_client.post(
        social_url,
        data={'access_token': 'provider-access-token'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {'authenticated': True}
    assert cycle_key_calls == [guest_session_key]
    assert api_client.cookies[settings.SESSION_COOKIE_NAME].value != (
        guest_session_key
    )
    assert not Session.objects.filter(session_key=guest_session_key).exists()
    assert not Cart.objects.filter(session_key=guest_session_key).exists()
    assert CartItem.objects.filter(
        cart__user=user,
        product_variant=variant,
        quantity=2,
    ).exists()


@pytest.mark.parametrize('provider', ['vk', 'yandex'])
def test_social_signup_merges_guest_cart(
    api_client,
    cart_add_url,
    listener_registration_consents,
    monkeypatch,
    provider,
    variant_factory,
):
    """Успешная social-регистрация также объединяет гостевую корзину."""
    email = f'new.{provider}.listener@example.test'
    uid = f'{provider}-new-uid'
    social_url = configure_social_provider(
        monkeypatch,
        provider,
        uid,
        email,
    )
    variant = variant_factory(product_type='merch')
    guest_session_key = create_guest_cart(
        api_client,
        cart_add_url,
        variant,
    )

    response = api_client.post(
        social_url,
        data={
            'access_token': 'provider-access-token',
            'create_account': True,
            'consents': listener_registration_consents,
        },
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    user = User.objects.get(email=email)
    assert SocialAccount.objects.filter(
        user=user,
        provider=provider,
        uid=uid,
    ).exists()
    assert not Cart.objects.filter(session_key=guest_session_key).exists()
    assert CartItem.objects.filter(
        cart__user=user,
        product_variant=variant,
        quantity=2,
    ).exists()


def test_social_login_merges_cart_after_session_flush(
    api_client,
    monkeypatch,
    user_factory,
    variant_factory,
):
    """Старая auth-session другого user не мешает merge после flush()."""
    previous_user = user_factory(
        email='previous.listener@example.test',
        username='previous_listener',
    )
    social_user = user_factory(
        email='social.listener@example.test',
        username='social_listener',
    )
    provider = 'vk'
    uid = 'vk-flush-uid'
    SocialAccount.objects.create(
        user=social_user,
        provider=provider,
        uid=uid,
    )
    social_url = configure_social_provider(
        monkeypatch,
        provider,
        uid,
        social_user.email,
    )

    api_client.force_login(previous_user)
    previous_session_key = api_client.cookies[
        settings.SESSION_COOKIE_NAME
    ].value
    variant = variant_factory(product_type='merch')
    guest_cart = Cart.objects.create(session_key=previous_session_key)
    CartItem.objects.create(
        cart=guest_cart,
        product_variant=variant,
        quantity=2,
    )
    flush_calls = []
    original_flush = SessionStore.flush

    def track_flush(session) -> None:
        flush_calls.append(session.session_key)
        original_flush(session)

    monkeypatch.setattr(SessionStore, 'flush', track_flush)

    response = api_client.post(
        social_url,
        data={'access_token': 'provider-access-token'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    assert flush_calls == [previous_session_key]
    assert api_client.cookies[settings.SESSION_COOKIE_NAME].value != (
        previous_session_key
    )
    assert not Session.objects.filter(
        session_key=previous_session_key,
    ).exists()
    assert not Cart.objects.filter(session_key=previous_session_key).exists()
    assert CartItem.objects.filter(
        cart__user=social_user,
        product_variant=variant,
        quantity=2,
    ).exists()


def test_social_login_without_initial_session_does_not_merge_new_session(
    api_client,
    monkeypatch,
    user_factory,
):
    """Отсутствующий pre-auth ключ не заменяется новым ключом allauth."""
    user = user_factory(
        email='no.session.listener@example.test',
        username='no_session_listener',
    )
    provider = 'yandex'
    uid = 'yandex-no-session-uid'
    SocialAccount.objects.create(user=user, provider=provider, uid=uid)
    social_url = configure_social_provider(
        monkeypatch,
        provider,
        uid,
        user.email,
    )
    assert settings.SESSION_COOKIE_NAME not in api_client.cookies

    with patch.object(
        CartService,
        'merge_carts',
        wraps=CartService.merge_carts,
    ) as merge_carts:
        response = api_client.post(
            social_url,
            data={'access_token': 'provider-access-token'},
            format='json',
        )

    assert response.status_code == status.HTTP_200_OK
    merge_carts.assert_called_once_with(user, None)
    assert settings.SESSION_COOKIE_NAME in api_client.cookies
    assert not Cart.objects.filter(user=user).exists()
    assert not Cart.objects.filter(user__isnull=True).exists()


@pytest.mark.parametrize('provider', ['vk', 'yandex'])
def test_failed_social_login_preserves_guest_cart(
    api_client,
    cart_add_url,
    monkeypatch,
    provider,
    variant_factory,
):
    """Неуспешный социальный вход не запускает merge и сохраняет корзину."""
    social_url = configure_social_provider(
        monkeypatch,
        provider,
        f'{provider}-failed-uid',
        f'{provider}.failed@example.test',
    )
    variant = variant_factory(product_type='merch')
    guest_session_key = create_guest_cart(
        api_client,
        cart_add_url,
        variant,
    )

    with patch.object(
        CartService,
        'merge_carts',
        wraps=CartService.merge_carts,
    ) as merge_carts:
        response = api_client.post(social_url, data={}, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.data['error_code'] == 'oauth_auth_failed'
    merge_carts.assert_not_called()
    assert Cart.objects.filter(
        session_key=guest_session_key,
        user__isnull=True,
    ).exists()
    assert CartItem.objects.filter(
        cart__session_key=guest_session_key,
        product_variant=variant,
        quantity=2,
    ).exists()
