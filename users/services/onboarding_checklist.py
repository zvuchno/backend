"""Сервисный модуль для формирования статусов чек-листа онбординга.

Содержит логику проверки готовности профиля артиста или лейбла
к продажам на витрине (заполнение реквизитов, интеграция с доставкой,
подключение уведомлений и создание/публикация товаров).
"""

from django.db.models import Q

from common.access import managed_artist_q
from common.services import get_artist_publication_readiness

from store.models import Product
from users.models import ArtistProfileType, ArtistShippingPoint

ONBOARDING_STEPS = (
    'add_first_product',
    'payout_details',
    'cdek_integration',
    'telegram_bot',
    'publish_first_product',
    'email_verified',
    'artist_cover',
)


def get_onboarding_checklist(user) -> dict[str, bool]:
    """Возвращает состояние выполнения шагов онбординга для витрины.

    Проверяет пять ключевых условий готовности аккаунта:
    1. `add_first_product` — наличие хотя бы одного активного товара
       (у самого пользователя или у подконтрольных артистов);
    2. `payout_details` — готовность юридического профиля к верификации;
    3. `cdek_integration` — наличие и активность способов доставки (курьер/СДЭК
       или актуальные самовывозы);
    4. `telegram_bot` — привязка Telegram-чата для уведомлений;
    5. `publish_first_product` — наличие хотя бы одного опубликованного товара.
    """
    artist = getattr(user, 'artist_profile', None)
    if not artist:
        return dict.fromkeys(ONBOARDING_STEPS, False)

    readiness = get_artist_publication_readiness(artist)

    # ПВЗ артиста, если у него включена своя доставка, иначе ПВЗ лейбла
    has_shipping_point = artist.effective_shipping_point is not None

    if (
        not has_shipping_point
        and artist.profile_type == ArtistProfileType.LABEL
    ):
        # включена доставка СДЭК и настроен ПВЗ
        # (свой или хотя бы одного подопечного, если это лейбл)
        has_shipping_point = (
            ArtistShippingPoint.objects
            .filter(
                artist__label=artist,
                artist__store_settings__shipping_enabled=True,
            )
            .exclude(Q(pvz_code='') | Q(city_code=''))
            .exists()
        )

    return {
        'add_first_product': Product.objects.filter(
            _managed_products_q(user),
        ).exists(),
        # используем признак готовности к продаже цифры в качестве
        # подтверждения ввода и верификации необходимых данных
        'payout_details': readiness.can_publish_digital,
        'cdek_integration': has_shipping_point,
        'telegram_bot': bool(artist.telegram_chat_id),
        'publish_first_product': Product.objects.filter(
            _managed_products_q(user, published=True),
        ).exists(),
        'email_verified': bool(user.is_email_verified),
        'artist_cover': bool(artist.cover),
    }


def _managed_products_q(user, *, published: bool = False) -> Q:
    """Строит условие: активный товар доступного пользователю артиста."""
    album_q = managed_artist_q(user, prefix='album__artist') & Q(
        album__is_active=True,
    )
    merch_q = managed_artist_q(user, prefix='merch__artist') & Q(
        merch__is_active=True,
    )

    if published:
        album_q &= Q(album__is_published=True)
        merch_q &= Q(merch__is_published=True)

    return album_q | merch_q
