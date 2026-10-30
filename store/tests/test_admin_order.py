"""Тесты безопасности отображения заказов в админке."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.contrib import admin

from store.admin.order import OrderItemInline
from store.models import OrderItem


def test_order_item_product_link_escapes_html(monkeypatch):
    """HTML в названии варианта не исполняется в админке."""
    malicious_name = '<img src=x onerror=alert(1)>'

    variant = MagicMock()
    variant.__str__.return_value = malicious_name

    album = SimpleNamespace(
        id=123,
        _meta=SimpleNamespace(
            app_label='store',
            model_name='album',
        ),
    )
    variant.product = SimpleNamespace(
        album=album,
        track=None,
        merch=None,
    )

    order_item = SimpleNamespace(product_variant=variant)

    monkeypatch.setattr(
        'store.admin.order.reverse',
        lambda *args, **kwargs: '/admin/store/album/123/change/',
    )

    inline = OrderItemInline(OrderItem, admin.site)
    result = inline.display_product_link(order_item)

    assert result == (
        '<a href="/admin/store/album/123/change/">'
        '&lt;img src=x onerror=alert(1)&gt;'
        '</a>'
    )
