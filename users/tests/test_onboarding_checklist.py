"""Тесты сервиса чек-листа онбординга."""

import pytest
from django.contrib.auth import get_user_model

from store.models import MerchKind
from store.tests.scenarios import (
    create_album_product,
    create_carrier_product,
    create_merch_product,
)
from users.models import ArtistShippingPoint, ArtistStoreSettings
from users.services.onboarding_checklist import (
    ONBOARDING_STEPS,
    get_onboarding_checklist,
)
from users.tests.factories import (
    ArtistProfileFactory,
    LabelUserFactory,
    UserFactory,
)
from users.tests.helpers import create_artist_legal_profile

User = get_user_model()

pytestmark = pytest.mark.django_db


# =================================
# Локальные хелперы и фикстуры
# =================================
def configure_shipping(
    profile,
    *,
    enabled=True,
    pvz_code='TEST-PVZ-001',
    city_code='44',
):
    """Настраивает доставку СДЭК профиля напрямую в БД."""
    ArtistStoreSettings.objects.update_or_create(
        artist=profile,
        defaults={'shipping_enabled': enabled},
    )
    return ArtistShippingPoint.objects.update_or_create(
        artist=profile,
        defaults={
            'pvz_code': pvz_code,
            'city_code': city_code,
            'city': 'Москва',
            'address': 'ул. Тестовая, д. 1',
        },
    )[0]


def make_product(
    artist,
    *,
    kind='album',
    is_active=True,
    is_published=True,
):
    """Создаёт товар артиста и выставляет флаги на связанном контенте."""
    if kind == 'merch':
        product = create_merch_product(artist=artist)
    elif kind == 'carrier':
        carrier_kind, _ = MerchKind.objects.get_or_create(
            slug='vinyl',
            defaults={'name': 'Винил', 'is_carrier': True},
        )
        product = create_carrier_product(artist=artist, kind=carrier_kind)
    else:
        product = create_album_product(artist=artist)

    content = product.content
    type(content).objects.filter(pk=content.pk).update(
        is_active=is_active,
        is_published=is_published,
    )
    return product


@pytest.fixture
def checklist():
    """Возвращает функцию расчёта чек-листа по свежему объекту пользователя.

    Пользователь перечитывается из БД, чтобы reverse OneToOne-связи
    (store_settings, shipping_point) не отдавали закешированные значения.
    """

    def get(user) -> dict[str, bool]:
        return get_onboarding_checklist(User.objects.get(pk=user.pk))

    return get


@pytest.fixture
def label_user():
    """Пользователь с профилем лейбла."""
    return LabelUserFactory()


# =================================
# Пользователь без профиля
# =================================
class TestWithoutProfile:
    """Пользователь без профиля артиста или лейбла."""

    def test_all_steps_false(self, checklist):
        """Все шаги не выполнены."""
        assert checklist(UserFactory()) == {
            'add_first_product': False,
            'payout_details': False,
            'cdek_integration': False,
            'telegram_bot': False,
            'publish_first_product': False,
            'email_verified': False,
            'artist_cover': False,
        }


# =================================
# cdek_integration
# =================================
class TestCdekIntegrationArtist:
    """Шаг cdek_integration для артиста."""

    def test_no_settings(self, checklist):
        """Без настроек доставки шаг не выполнен."""
        artist = ArtistProfileFactory()
        assert checklist(artist.user)['cdek_integration'] is False

    def test_enabled_and_configured(self, checklist):
        """Включённая доставка и настроенный ПВЗ засчитываются."""
        artist = ArtistProfileFactory()
        configure_shipping(artist)
        assert checklist(artist.user)['cdek_integration'] is True

    def test_disabled(self, checklist):
        """Настроенный ПВЗ при выключенной доставке не засчитывается."""
        artist = ArtistProfileFactory()
        configure_shipping(artist, enabled=False)
        assert checklist(artist.user)['cdek_integration'] is False

    @pytest.mark.parametrize(
        ('pvz_code', 'city_code'),
        [('', '44'), ('MSK1', ''), ('', '')],
        ids=['no_pvz', 'no_city', 'no_both'],
    )
    def test_enabled_with_empty_codes(self, checklist, pvz_code, city_code):
        """Включённая доставка с пустыми кодами не засчитывается."""
        artist = ArtistProfileFactory()
        configure_shipping(artist, pvz_code=pvz_code, city_code=city_code)
        assert checklist(artist.user)['cdek_integration'] is False

    def test_inherits_label_point(self, checklist, label_user):
        """Артист под лейблом использует ПВЗ лейбла."""
        label = label_user.artist_profile
        configure_shipping(label)
        artist = ArtistProfileFactory(label=label)
        assert checklist(artist.user)['cdek_integration'] is True

    def test_label_not_configured(self, checklist, label_user):
        """Если ПВЗ нет ни у артиста, ни у лейбла, шаг не выполнен."""
        artist = ArtistProfileFactory(label=label_user.artist_profile)
        assert checklist(artist.user)['cdek_integration'] is False

    def test_sibling_point_ignored(self, checklist, label_user):
        """ПВЗ другого подопечного того же лейбла не учитывается."""
        label = label_user.artist_profile
        artist = ArtistProfileFactory(label=label)
        configure_shipping(ArtistProfileFactory(label=label))
        assert checklist(artist.user)['cdek_integration'] is False


class TestCdekIntegrationLabel:
    """Шаг cdek_integration для лейбла."""

    def test_own_point(self, checklist, label_user):
        """Собственный настроенный ПВЗ лейбла засчитывается."""
        configure_shipping(label_user.artist_profile)
        assert checklist(label_user)['cdek_integration'] is True

    def test_nothing_configured(self, checklist, label_user):
        """Без собственного ПВЗ и без подопечных шаг не выполнен."""
        assert checklist(label_user)['cdek_integration'] is False

    def test_own_point_disabled(self, checklist, label_user):
        """Свой ПВЗ при выключенной доставке не засчитывается."""
        configure_shipping(label_user.artist_profile, enabled=False)
        assert checklist(label_user)['cdek_integration'] is False

    def test_managed_artist_configured(self, checklist, label_user):
        """Достаточно настроенного ПВЗ у одного подопечного."""
        managed = ArtistProfileFactory(label=label_user.artist_profile)
        configure_shipping(managed)
        assert checklist(label_user)['cdek_integration'] is True

    def test_managed_artist_without_account(self, checklist, label_user):
        """Подопечный без аккаунта тоже учитывается."""
        managed = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        configure_shipping(managed)
        assert checklist(label_user)['cdek_integration'] is True

    def test_managed_artist_disabled(self, checklist, label_user):
        """У подопечного с выключенной доставкой ПВЗ не засчитывается."""
        managed = ArtistProfileFactory(label=label_user.artist_profile)
        configure_shipping(managed, enabled=False)
        assert checklist(label_user)['cdek_integration'] is False

    def test_managed_artist_empty_codes(self, checklist, label_user):
        """Включённая доставка с пустыми кодами у подопечного не считается."""
        managed = ArtistProfileFactory(label=label_user.artist_profile)
        configure_shipping(managed, pvz_code='', city_code='')
        assert checklist(label_user)['cdek_integration'] is False

    def test_one_of_several_managed_is_enough(self, checklist, label_user):
        """Среди нескольких подопечных хватает одного настроенного."""
        label = label_user.artist_profile
        ArtistProfileFactory(label=label)
        configure_shipping(ArtistProfileFactory(label=label), enabled=False)
        configure_shipping(ArtistProfileFactory(label=label))
        assert checklist(label_user)['cdek_integration'] is True

    def test_foreign_label_managed_ignored(self, checklist, label_user):
        """Подопечные чужого лейбла не учитываются."""
        other_label = LabelUserFactory().artist_profile
        configure_shipping(ArtistProfileFactory(label=other_label))
        assert checklist(label_user)['cdek_integration'] is False


# =================================
# telegram_bot и payout_details
# =================================
class TestTelegramBot:
    """Шаг telegram_bot."""

    def test_chat_id_toggles_step(self, checklist):
        """Шаг выполнен, когда привязан Telegram-чат."""
        artist = ArtistProfileFactory()
        assert checklist(artist.user)['telegram_bot'] is False

        artist.telegram_chat_id = 123456
        artist.save(update_fields=['telegram_chat_id'])
        assert checklist(artist.user)['telegram_bot'] is True


@pytest.mark.usefixtures('publication_readiness_enabled')
class TestPayoutDetails:
    """Шаг payout_details (готовность к цифровым продажам)."""

    def test_not_ready(self, checklist):
        """Без юридического профиля шаг не выполнен."""
        artist = ArtistProfileFactory()
        assert checklist(artist.user)['payout_details'] is False

    def test_ready_artist(self, checklist, ready_artist_factory):
        """Верифицированный артист проходит шаг."""
        artist = ready_artist_factory()
        assert checklist(artist.user)['payout_details'] is True

    def test_ready_label(self, checklist, ready_label_factory):
        """Верифицированный лейбл проходит шаг."""
        assert checklist(ready_label_factory())['payout_details'] is True

    def test_independent_of_email_and_cover(self, checklist):
        """Payout_details не зависит от email и обложки."""
        artist = ArtistProfileFactory(
            cover='',
            user__is_email_verified=False,
        )
        create_artist_legal_profile(
            artist.default_payout_recipient,
            is_verified=True,
        )

        result = checklist(artist.user)

        assert result['payout_details'] is True
        assert result['email_verified'] is False
        assert result['artist_cover'] is False

    def test_managed_artist_uses_label_recipient(
        self,
        checklist,
        ready_label_factory,
    ):
        """У подопечного шаг определяется реквизитами лейбла."""
        label_user = ready_label_factory()
        artist = ArtistProfileFactory(label=label_user.artist_profile)
        assert checklist(artist.user)['payout_details'] is True

    def test_managed_artist_own_profile_ignored(self, checklist, label_user):
        """Собственные реквизиты подопечного не учитываются."""
        artist = ArtistProfileFactory(label=label_user.artist_profile)
        create_artist_legal_profile(artist.user, is_verified=True)
        assert checklist(artist.user)['payout_details'] is False

    def test_unverified_profile(self, checklist):
        """Неверифицированный юридический профиль шаг не закрывает."""
        artist = ArtistProfileFactory()
        create_artist_legal_profile(artist.user, is_verified=False)
        assert checklist(artist.user)['payout_details'] is False


# =================================
# add_first_product и publish_first_product
# =================================
@pytest.mark.parametrize('kind', ['album', 'merch', 'carrier'])
class TestProductSteps:
    """Шаги add_first_product и publish_first_product."""

    def test_no_products(self, checklist, kind):
        """Без товаров оба шага не выполнены."""
        artist = ArtistProfileFactory()
        result = checklist(artist.user)
        assert result['add_first_product'] is False
        assert result['publish_first_product'] is False

    @pytest.mark.parametrize(
        ('is_active', 'is_published', 'expected_add', 'expected_publish'),
        [
            (True, True, True, True),
            (True, False, True, False),
            (False, True, False, False),
            (False, False, False, False),
        ],
        ids=['published', 'draft', 'inactive_published', 'inactive_draft'],
    )
    def test_flags(
        self,
        checklist,
        kind,
        is_active,
        is_published,
        expected_add,
        expected_publish,
    ):
        """Шаги зависят от is_active и is_published контента товара."""
        artist = ArtistProfileFactory()
        make_product(
            artist,
            kind=kind,
            is_active=is_active,
            is_published=is_published,
        )

        result = checklist(artist.user)

        assert result['add_first_product'] is expected_add
        assert result['publish_first_product'] is expected_publish

    def test_label_sees_own_products(self, checklist, label_user, kind):
        """Лейбл видит товары собственного профиля."""
        make_product(label_user.artist_profile, kind=kind)
        result = checklist(label_user)
        assert result['add_first_product'] is True
        assert result['publish_first_product'] is True

    def test_label_sees_managed_products(self, checklist, label_user, kind):
        """Лейбл видит товары подопечного с аккаунтом."""
        managed = ArtistProfileFactory(label=label_user.artist_profile)
        make_product(managed, kind=kind)
        result = checklist(label_user)
        assert result['add_first_product'] is True
        assert result['publish_first_product'] is True

    def test_label_sees_managed_without_account(
        self,
        checklist,
        label_user,
        kind,
    ):
        """Лейбл видит товары подопечного без аккаунта."""
        managed = ArtistProfileFactory(
            user=None,
            label=label_user.artist_profile,
        )
        make_product(managed, kind=kind)
        result = checklist(label_user)
        assert result['add_first_product'] is True
        assert result['publish_first_product'] is True

    def test_label_does_not_see_foreign_label_products(
        self,
        checklist,
        label_user,
        kind,
    ):
        """Лейбл не видит товары подопечных чужого лейбла."""
        other_label = LabelUserFactory().artist_profile
        make_product(ArtistProfileFactory(label=other_label), kind=kind)
        result = checklist(label_user)
        assert result['add_first_product'] is False
        assert result['publish_first_product'] is False

    def test_artist_does_not_see_foreign_products(self, checklist, kind):
        """Артист не видит товары посторонних артистов."""
        artist = ArtistProfileFactory()
        make_product(ArtistProfileFactory(), kind=kind)
        result = checklist(artist.user)
        assert result['add_first_product'] is False
        assert result['publish_first_product'] is False

    def test_artist_does_not_see_label_and_sibling(
        self,
        checklist,
        label_user,
        kind,
    ):
        """Артист под лейблом не видит товары лейбла и соседей."""
        label = label_user.artist_profile
        artist = ArtistProfileFactory(label=label)
        make_product(label, kind=kind)
        make_product(ArtistProfileFactory(label=label), kind=kind)

        result = checklist(artist.user)

        assert result['add_first_product'] is False
        assert result['publish_first_product'] is False


class TestEmailVerified:
    """Check email_verified."""

    @pytest.mark.parametrize('is_verified', [True, False])
    def test_artist(self, checklist, is_verified):
        """Подтверждение email учётной записи артиста."""
        artist = ArtistProfileFactory(user__is_email_verified=is_verified)
        assert checklist(artist.user)['email_verified'] is is_verified

    @pytest.mark.parametrize('is_verified', [True, False])
    def test_label(self, checklist, is_verified):
        """Подтверждение email учётной записи лейбла."""
        label_user = LabelUserFactory(is_email_verified=is_verified)
        assert checklist(label_user)['email_verified'] is is_verified


class TestArtistCover:
    """Шаг artist_cover."""

    def test_cover_uploaded(self, checklist):
        """Загруженная обложка засчитывается."""
        artist = ArtistProfileFactory()
        assert checklist(artist.user)['artist_cover'] is True

    @pytest.mark.parametrize('empty_cover', ['', None], ids=['blank', 'null'])
    def test_no_cover(self, checklist, empty_cover):
        """Пустая обложка не засчитывается."""
        artist = ArtistProfileFactory(cover=empty_cover)
        assert checklist(artist.user)['artist_cover'] is False

    def test_label_own_cover_only(self, checklist, label_user):
        """У лейбла считается только собственная обложка, не подопечных."""
        label = label_user.artist_profile
        label.cover = ''
        label.save(update_fields=['cover'])
        ArtistProfileFactory(label=label)  # у подопечного обложка есть

        assert checklist(label_user)['artist_cover'] is False


class TestChecklistContract:
    """Форма результата: набор ключей чек-листа."""

    def test_keys_match_steps_constant(self, checklist):
        """Ключи результата для профиля совпадают с ONBOARDING_STEPS."""
        artist = ArtistProfileFactory()
        assert set(checklist(artist.user)) == set(ONBOARDING_STEPS)
