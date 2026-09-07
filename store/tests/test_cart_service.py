from datetime import timedelta

import pytest
from django.utils import timezone

from store.constants import STALE_ANONYMOUS_CART_DAYS
from store.models import Cart
from store.services.cart_service import CartService
from store.tasks import delete_stale_anonymous_carts

pytestmark = pytest.mark.django_db


@pytest.fixture
def cart(user) -> Cart:
    """Пустая корзина авторизованного пользователя."""
    return Cart.objects.create(user=user)


@pytest.fixture
def merch_variant(variant_factory):
    """Вариант мерча в наличии."""
    return variant_factory('merch', stock=10)


class TestCartServiceTouch:
    """Тесты на обновление updated_at корзины сервисом CartService."""

    def test_add_to_cart_touches_cart_on_new_item(self, cart, merch_variant):
        """Новый товар добавлен в корзину → updated_at обновляется."""
        old_updated_at = cart.updated_at

        CartService.add_to_cart(cart, merch_variant, quantity=1)
        cart.refresh_from_db()

        assert cart.updated_at > old_updated_at

    def test_add_to_cart_touches_cart_on_existing_item(
        self,
        cart,
        merch_variant,
    ):
        """Количество товара увеличено → updated_at обновляется."""
        CartService.add_to_cart(cart, merch_variant, quantity=1)
        cart.refresh_from_db()
        old_updated_at = cart.updated_at

        CartService.add_to_cart(cart, merch_variant, quantity=1)
        cart.refresh_from_db()

        assert cart.updated_at > old_updated_at

    def test_update_cart_items_touches_cart_only_on_change(
        self,
        cart,
        merch_variant,
    ):
        """Количество товара изменилось → updated_at обновляется."""
        item = CartService.add_to_cart(cart, merch_variant, quantity=1)
        cart.refresh_from_db()
        old_updated_at = cart.updated_at

        # то же количество — изменений нет, touch не должен произойти
        CartService.update_cart_items(
            cart,
            [{'product_variant': merch_variant, 'quantity': item.quantity}],
        )
        cart.refresh_from_db()
        assert cart.updated_at == old_updated_at

        # реальное изменение количества — touch должен произойти
        CartService.update_cart_items(
            cart,
            [
                {
                    'product_variant': merch_variant,
                    'quantity': item.quantity + 1,
                },
            ],
        )
        cart.refresh_from_db()
        assert cart.updated_at > old_updated_at

    def test_remove_from_cart_touches_cart_only_when_deleted(
        self,
        cart,
        merch_variant,
    ):
        """Товар удалён из корзины → updated_at обновляется, иначе — нет."""
        CartService.add_to_cart(cart, merch_variant, quantity=1)
        cart.refresh_from_db()
        old_updated_at = cart.updated_at

        # несуществующий вариант — ничего не удалено, touch быть не должно
        result = CartService.remove_from_cart(cart, variant_id=999999)
        cart.refresh_from_db()
        assert result is False
        assert cart.updated_at == old_updated_at

        result = CartService.remove_from_cart(
            cart,
            variant_id=merch_variant.id,
        )
        cart.refresh_from_db()
        assert result is True
        assert cart.updated_at > old_updated_at


def _make_cart(*, user=None, session_key=None, updated_days_ago=0) -> Cart:
    """Создаёт корзину и откатывает updated_at назад через queryset.update."""
    cart = Cart.objects.create(user=user, session_key=session_key)
    if updated_days_ago:
        past = timezone.now() - timedelta(days=updated_days_ago)
        Cart.objects.filter(pk=cart.pk).update(updated_at=past)
        cart.refresh_from_db()
    return cart


class TestDeleteStaleAnonymousCarts:
    """Тесты для фоновой очистки брошенных гостевых корзин."""

    def test_deletes_stale_anonymous_cart(self):
        """Не обновлялась дольше STALE_ANONYMOUS_CART_DAYS → удаляется."""
        stale = _make_cart(
            session_key='stale-session',
            updated_days_ago=STALE_ANONYMOUS_CART_DAYS + 1,
        )

        delete_stale_anonymous_carts()

        assert not Cart.objects.filter(pk=stale.pk).exists()

    def test_keeps_fresh_anonymous_cart(self):
        """Гостевая корзина обновлялась недавно → не удаляется."""
        fresh = _make_cart(
            session_key='fresh-session',
            updated_days_ago=STALE_ANONYMOUS_CART_DAYS - 1,
        )

        delete_stale_anonymous_carts()

        assert Cart.objects.filter(pk=fresh.pk).exists()

    def test_keeps_stale_cart_with_user(self, user):
        """Корзина привязана к пользователю → не удаляется."""
        user_cart = _make_cart(
            user=user,
            updated_days_ago=STALE_ANONYMOUS_CART_DAYS + 10,
        )

        delete_stale_anonymous_carts()

        assert Cart.objects.filter(pk=user_cart.pk).exists()

    def test_borderline_cart_not_deleted(self):
        """Корзина чуть свежее cutoff → не удаляется."""
        borderline = _make_cart(session_key='borderline-session')
        Cart.objects.filter(pk=borderline.pk).update(
            updated_at=timezone.now()
            - timedelta(days=STALE_ANONYMOUS_CART_DAYS)
            + timedelta(minutes=1),
        )

        delete_stale_anonymous_carts()

        assert Cart.objects.filter(pk=borderline.pk).exists()
