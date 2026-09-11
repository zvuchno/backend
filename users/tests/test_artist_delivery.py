"""Тесты API настроек доставки управляемых профилей."""

from datetime import date
from http import HTTPStatus

import pytest

from users.models import (
    ArtistPickupPoint,
    ArtistShippingPoint,
    ArtistStoreSettings,
)

pytestmark = pytest.mark.django_db


class TestArtistPickupPointAPI:
    """Тесты управления точками самовывоза."""

    def test_artist_creates_pickup_point_for_self(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_list_url,
    ):
        """Артист создаёт точку самовывоза собственного профиля."""
        profile = artist_user.artist_profile

        response = artist_client.post(
            managed_pickup_point_list_url(profile),
            data={
                'enabled': True,
                'points': [
                    {
                        'address': 'г. Курган, ул. Ленина, 10',
                        'pickup_date': '2026-08-15',
                        'is_active': True,
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        pickup_point = ArtistPickupPoint.objects.get(
            artist=profile,
        )

        assert pickup_point.address == 'г. Курган, ул. Ленина, 10'
        assert pickup_point.pickup_date == date(2026, 8, 15)
        assert pickup_point.is_active is True
        assert response.data == {
            'enabled': True,
            'points': [
                {
                    'id': pickup_point.id,
                    'address': 'г. Курган, ул. Ленина, 10',
                    'pickup_date': '2026-08-15',
                    'is_active': True,
                },
            ],
        }

    def test_artist_gets_own_pickup_points(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_list_url,
    ):
        """Артист получает точки самовывоза собственного профиля."""
        profile = artist_user.artist_profile

        first_point = ArtistPickupPoint.objects.create(
            artist=profile,
            address='Первая точка',
            pickup_date='2026-08-15',
        )
        second_point = ArtistPickupPoint.objects.create(
            artist=profile,
            address='Вторая точка',
            pickup_date='2026-08-16',
            is_active=False,
        )

        response = artist_client.get(
            managed_pickup_point_list_url(profile),
        )

        assert response.status_code == HTTPStatus.OK
        assert response.data['enabled'] is False

        results = response.data['points']

        assert [item['id'] for item in results] == [
            first_point.id,
            second_point.id,
        ]
        assert results[1]['is_active'] is False

    def test_artist_updates_pickup_point(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_detail_url,
    ):
        """Артист изменяет точку самовывоза собственного профиля."""
        profile = artist_user.artist_profile
        pickup_point = ArtistPickupPoint.objects.create(
            artist=profile,
            address='Старый адрес',
            pickup_date='2026-08-15',
        )

        response = artist_client.patch(
            managed_pickup_point_detail_url(
                profile,
                pickup_point,
            ),
            data={
                'address': 'Новый адрес',
                'is_active': False,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        pickup_point.refresh_from_db()

        assert pickup_point.address == 'Новый адрес'
        assert pickup_point.is_active is False
        assert pickup_point.pickup_date == date(2026, 8, 15)

    def test_artist_deletes_pickup_point(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_detail_url,
    ):
        """Артист удаляет точку самовывоза собственного профиля."""
        profile = artist_user.artist_profile
        pickup_point = ArtistPickupPoint.objects.create(
            artist=profile,
            address='Точка для удаления',
            pickup_date='2026-08-15',
        )

        response = artist_client.delete(
            managed_pickup_point_detail_url(
                profile,
                pickup_point,
            ),
        )

        assert response.status_code == HTTPStatus.NO_CONTENT
        assert not ArtistPickupPoint.objects.filter(
            pk=pickup_point.pk,
        ).exists()

    def test_artist_cannot_access_foreign_profile_pickup_points(
        self,
        artist_client,
        other_artist_user,
        managed_pickup_point_list_url,
    ):
        """Артист не получает доступ к точкам чужого профиля."""
        response = artist_client.get(
            managed_pickup_point_list_url(
                other_artist_user.artist_profile,
            ),
        )

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_pickup_point_detail_is_scoped_by_profile(
        self,
        artist_client,
        artist_user,
        other_artist_user,
        managed_pickup_point_detail_url,
    ):
        """Точку нельзя получить через URL другого профиля."""
        own_profile = artist_user.artist_profile
        foreign_profile = other_artist_user.artist_profile

        pickup_point = ArtistPickupPoint.objects.create(
            artist=own_profile,
            address='Своя точка',
            pickup_date='2026-08-15',
        )

        response = artist_client.get(
            managed_pickup_point_detail_url(
                foreign_profile,
                pickup_point,
            ),
        )

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_label_creates_pickup_point_for_managed_artist(
        self,
        label_client,
        label_created_artist,
        managed_pickup_point_list_url,
    ):
        """Лейбл создаёт точку самовывоза управляемого артиста."""
        response = label_client.post(
            managed_pickup_point_list_url(label_created_artist),
            data={
                'enabled': True,
                'points': [
                    {
                        'address': 'Пункт управляемого артиста',
                        'pickup_date': '2026-08-20',
                        'is_active': True,
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        pickup_point = ArtistPickupPoint.objects.get(
            artist=label_created_artist,
        )

        assert pickup_point.address == 'Пункт управляемого артиста'
        assert pickup_point.pickup_date == date(2026, 8, 20)
        assert pickup_point.is_active is True

        settings = ArtistStoreSettings.objects.get(
            artist=label_created_artist,
        )
        assert settings.pickup_enabled is True

    def test_label_creates_pickup_point_for_signed_artist(
        self,
        label_client,
        signed_artist_user,
        managed_pickup_point_list_url,
    ):
        """Лейбл управляет точками подключённого артиста."""
        profile = signed_artist_user.artist_profile

        response = label_client.post(
            managed_pickup_point_list_url(profile),
            data={
                'enabled': True,
                'points': [
                    {
                        'address': 'Пункт подключённого артиста',
                        'pickup_date': '2026-08-21',
                        'is_active': True,
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK
        assert ArtistPickupPoint.objects.filter(
            artist=profile,
            address='Пункт подключённого артиста',
        ).exists()

    def test_label_cannot_access_unmanaged_artist_pickup_points(
        self,
        label_client,
        other_artist_user,
        managed_pickup_point_list_url,
    ):
        """Лейбл не получает точки чужого артиста."""
        response = label_client.get(
            managed_pickup_point_list_url(
                other_artist_user.artist_profile,
            ),
        )

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_artist_cannot_create_duplicate_active_pickup_point(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_list_url,
    ):
        """Нельзя создать одинаковые активные точки одного артиста."""
        profile = artist_user.artist_profile
        point_data = {
            'address': 'Одинаковый адрес',
            'pickup_date': '2026-08-15',
            'is_active': True,
        }

        first_response = artist_client.post(
            managed_pickup_point_list_url(profile),
            data={
                'enabled': True,
                'points': [point_data],
            },
            format='json',
        )
        second_response = artist_client.post(
            managed_pickup_point_list_url(profile),
            data={
                'enabled': True,
                'points': [point_data],
            },
            format='json',
        )

        assert first_response.status_code == HTTPStatus.OK
        assert second_response.status_code == HTTPStatus.BAD_REQUEST
        assert second_response.data == {
            'points': [
                'Активные точки самовывоза не должны дублироваться.',
            ],
        }

    def test_different_artists_can_have_same_active_pickup_point(
        self,
        artist_client,
        artist_user,
        other_artist_user,
        managed_pickup_point_list_url,
    ):
        """Разным артистам разрешены одинаковые точки самовывоза."""
        point_data = {
            'address': 'Общий концертный зал',
            'pickup_date': '2026-08-15',
            'is_active': True,
        }

        ArtistPickupPoint.objects.create(
            artist=other_artist_user.artist_profile,
            **point_data,
        )

        response = artist_client.post(
            managed_pickup_point_list_url(
                artist_user.artist_profile,
            ),
            data={
                'enabled': True,
                'points': [point_data],
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

    def test_artist_creates_pickup_point_via_me_alias(
        self,
        artist_client,
        artist_user,
        artist_me_pickup_point_list_url,
    ):
        """Алиас me создаёт точку собственного профиля."""
        response = artist_client.post(
            artist_me_pickup_point_list_url,
            data={
                'enabled': True,
                'points': [
                    {
                        'address': 'Точка через me',
                        'pickup_date': '2026-08-15',
                        'is_active': True,
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK
        assert ArtistPickupPoint.objects.filter(
            artist=artist_user.artist_profile,
            address='Точка через me',
        ).exists()

    def test_me_alias_does_not_access_foreign_pickup_point(
        self,
        artist_client,
        other_artist_user,
        artist_me_pickup_point_detail_url,
    ):
        """Алиас me не получает точку чужого профиля."""
        pickup_point = ArtistPickupPoint.objects.create(
            artist=other_artist_user.artist_profile,
            address='Чужая точка',
            pickup_date='2026-08-15',
        )

        response = artist_client.get(
            artist_me_pickup_point_detail_url(pickup_point),
        )

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_label_me_alias_uses_label_own_profile(
        self,
        label_client,
        label_user,
        label_created_artist,
        artist_me_pickup_point_list_url,
    ):
        """Алиас me лейбла работает с собственным профилем лейбла."""
        response = label_client.post(
            artist_me_pickup_point_list_url,
            data={
                'enabled': True,
                'points': [
                    {
                        'address': 'Точка самого лейбла',
                        'pickup_date': '2026-08-15',
                        'is_active': True,
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        pickup_point = ArtistPickupPoint.objects.get(
            address='Точка самого лейбла',
        )

        assert pickup_point.artist == label_user.artist_profile
        assert pickup_point.artist != label_created_artist

    def test_artist_cannot_create_duplicate_active_pickup_point_without_date(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_list_url,
    ):
        """Нельзя создать одинаковые активные точки без даты."""
        profile = artist_user.artist_profile
        point_data = {
            'address': 'Постоянная точка',
            'pickup_date': None,
            'is_active': True,
        }

        first_response = artist_client.post(
            managed_pickup_point_list_url(profile),
            data={
                'enabled': True,
                'points': [point_data],
            },
            format='json',
        )
        second_response = artist_client.post(
            managed_pickup_point_list_url(profile),
            data={
                'enabled': True,
                'points': [point_data],
            },
            format='json',
        )

        assert first_response.status_code == HTTPStatus.OK
        assert second_response.status_code == HTTPStatus.BAD_REQUEST

    def test_updates_pickup_point_without_changing_enabled(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_list_url,
    ):
        """Точки можно изменить без повторной передачи enabled."""
        profile = artist_user.artist_profile
        settings = ArtistStoreSettings.objects.create(
            artist=profile,
            pickup_enabled=True,
        )
        pickup_point = ArtistPickupPoint.objects.create(
            artist=profile,
            address='Старый адрес',
            pickup_date='2026-08-15',
            is_active=True,
        )

        response = artist_client.post(
            managed_pickup_point_list_url(profile),
            data={
                'points': [
                    {
                        'id': pickup_point.id,
                        'address': 'Новый адрес',
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        pickup_point.refresh_from_db()
        settings.refresh_from_db()

        assert pickup_point.address == 'Новый адрес'
        assert settings.pickup_enabled is True

    def test_explicit_enable_rejects_deactivating_last_pickup_point(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_list_url,
    ):
        """Нельзя оставить самовывоз включённым без активных точек."""
        profile = artist_user.artist_profile
        pickup_point = ArtistPickupPoint.objects.create(
            artist=profile,
            address='Последняя точка',
            pickup_date='2026-08-15',
            is_active=True,
        )

        response = artist_client.post(
            managed_pickup_point_list_url(profile),
            data={
                'enabled': True,
                'points': [
                    {
                        'id': pickup_point.id,
                        'is_active': False,
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'enabled' in response.data

        pickup_point.refresh_from_db()
        assert pickup_point.is_active is True

    def test_deactivating_last_pickup_without_enabled_disables_pickup(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_list_url,
    ):
        """Без enabled деактивация последней точки выключает самовывоз."""
        profile = artist_user.artist_profile
        settings = ArtistStoreSettings.objects.create(
            artist=profile,
            pickup_enabled=True,
        )
        pickup_point = ArtistPickupPoint.objects.create(
            artist=profile,
            address='Последняя точка',
            pickup_date='2026-08-15',
            is_active=True,
        )

        response = artist_client.post(
            managed_pickup_point_list_url(profile),
            data={
                'points': [
                    {
                        'id': pickup_point.id,
                        'is_active': False,
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        pickup_point.refresh_from_db()
        settings.refresh_from_db()

        assert pickup_point.is_active is False
        assert settings.pickup_enabled is False

    def test_deactivating_last_pickup_point_disables_pickup(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_detail_url,
    ):
        """Отключение последней точки выключает самовывоз."""
        profile = artist_user.artist_profile

        settings = ArtistStoreSettings.objects.create(
            artist=profile,
            pickup_enabled=True,
        )
        pickup_point = ArtistPickupPoint.objects.create(
            artist=profile,
            address='Последняя точка',
            pickup_date='2026-09-10',
            is_active=True,
        )

        response = artist_client.patch(
            managed_pickup_point_detail_url(
                profile,
                pickup_point,
            ),
            data={
                'is_active': False,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        settings.refresh_from_db()

        assert settings.pickup_enabled is False

    def test_deleting_last_pickup_point_disables_pickup(
        self,
        artist_client,
        artist_user,
        managed_pickup_point_detail_url,
    ):
        """Удаление последней точки выключает самовывоз."""
        profile = artist_user.artist_profile

        settings = ArtistStoreSettings.objects.create(
            artist=profile,
            pickup_enabled=True,
        )
        pickup_point = ArtistPickupPoint.objects.create(
            artist=profile,
            address='Последняя точка',
            pickup_date='2026-09-10',
            is_active=True,
        )

        response = artist_client.delete(
            managed_pickup_point_detail_url(
                profile,
                pickup_point,
            ),
        )

        assert response.status_code == HTTPStatus.NO_CONTENT

        settings.refresh_from_db()

        assert settings.pickup_enabled is False


class TestArtistShippingPointAPI:
    """Тесты управления ПВЗ отправления."""

    def test_get_returns_empty_shipping_settings(
        self,
        artist_without_shipping_point_client,
        artist_without_shipping_point,
        managed_shipping_point_url,
    ):
        """При отсутствии ПВЗ API возвращает выключенные настройки."""
        response = artist_without_shipping_point_client.get(
            managed_shipping_point_url(
                artist_without_shipping_point.artist_profile,
            ),
        )

        assert response.status_code == HTTPStatus.OK
        assert response.data == {
            'enabled': False,
            'point': None,
        }

    def test_put_creates_shipping_point(
        self,
        artist_without_shipping_point_client,
        artist_without_shipping_point,
        managed_shipping_point_url,
    ):
        """PUT создаёт ПВЗ отправления."""
        profile = artist_without_shipping_point.artist_profile

        response = artist_without_shipping_point_client.put(
            managed_shipping_point_url(profile),
            data={
                'point': {
                    'pvz_code': 'KGN12',
                    'city_code': '123',
                    'city': 'Курган',
                    'address': 'ул. Гоголя, 55',
                },
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK

        shipping_point = ArtistShippingPoint.objects.get(
            artist=profile,
        )

        assert shipping_point.pvz_code == 'KGN12'
        assert shipping_point.city_code == '123'
        assert shipping_point.city == 'Курган'
        assert shipping_point.address == 'ул. Гоголя, 55'
        assert response.data == {
            'enabled': False,
            'point': {
                'pvz_code': 'KGN12',
                'city_code': '123',
                'city': 'Курган',
                'address': 'ул. Гоголя, 55',
            },
        }

    def test_repeated_put_updates_existing_shipping_point(
        self,
        artist_client,
        artist_user,
        managed_shipping_point_url,
    ):
        """Повторный PUT обновляет ПВЗ, не меняя состояние СДЭК."""
        profile = artist_user.artist_profile
        shipping_point = profile.shipping_point
        settings, _ = ArtistStoreSettings.objects.update_or_create(
            artist=profile,
            defaults={
                'shipping_enabled': True,
            },
        )

        response = artist_client.put(
            managed_shipping_point_url(profile),
            data={
                'point': {
                    'pvz_code': 'NEW2',
                    'city_code': '456',
                    'city': 'Тюмень',
                    'address': 'Новый адрес',
                },
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK
        assert (
            ArtistShippingPoint.objects.filter(
                artist=profile,
            ).count()
            == 1
        )

        shipping_point.refresh_from_db()
        settings.refresh_from_db()

        assert shipping_point.pvz_code == 'NEW2'
        assert shipping_point.city_code == '456'
        assert shipping_point.city == 'Тюмень'
        assert shipping_point.address == 'Новый адрес'
        assert settings.shipping_enabled is True

    def test_get_returns_existing_shipping_point(
        self,
        artist_client,
        artist_user,
        managed_shipping_point_url,
    ):
        """Артист получает состояние СДЭК и сохранённый ПВЗ."""
        profile = artist_user.artist_profile
        shipping_point = profile.shipping_point

        response = artist_client.get(
            managed_shipping_point_url(profile),
        )

        assert response.status_code == HTTPStatus.OK
        assert response.data == {
            'enabled': False,
            'point': {
                'pvz_code': shipping_point.pvz_code,
                'city_code': shipping_point.city_code,
                'city': shipping_point.city,
                'address': shipping_point.address,
            },
        }

    def test_delete_removes_shipping_point(
        self,
        artist_client,
        artist_user,
        managed_shipping_point_url,
    ):
        """DELETE удаляет ПВЗ отправления."""
        profile = artist_user.artist_profile
        shipping_point_id = profile.shipping_point.id

        response = artist_client.delete(
            managed_shipping_point_url(profile),
        )

        assert response.status_code == HTTPStatus.NO_CONTENT
        assert not ArtistShippingPoint.objects.filter(
            pk=shipping_point_id,
        ).exists()

    def test_delete_is_idempotent(
        self,
        artist_without_shipping_point_client,
        artist_without_shipping_point,
        managed_shipping_point_url,
    ):
        """DELETE отсутствующего ПВЗ остаётся успешным."""
        response = artist_without_shipping_point_client.delete(
            managed_shipping_point_url(
                artist_without_shipping_point.artist_profile,
            ),
        )

        assert response.status_code == HTTPStatus.NO_CONTENT
        assert not ArtistShippingPoint.objects.filter(
            artist=artist_without_shipping_point.artist_profile,
        ).exists()

    def test_label_creates_managed_artist_shipping_point(
        self,
        label_client,
        label_created_artist,
        managed_shipping_point_url,
    ):
        """Лейбл настраивает и включает СДЭК управляемому артисту."""
        response = label_client.put(
            managed_shipping_point_url(label_created_artist),
            data={
                'enabled': True,
                'point': {
                    'pvz_code': 'MSK100',
                    'city_code': '44',
                    'city': 'Москва',
                    'address': 'ул. Тестовая, 1',
                },
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK
        assert ArtistShippingPoint.objects.filter(
            artist=label_created_artist,
            pvz_code='MSK100',
        ).exists()

        settings = ArtistStoreSettings.objects.get(
            artist=label_created_artist,
        )
        assert settings.shipping_enabled is True

    def test_label_cannot_access_unmanaged_artist_shipping_point(
        self,
        label_client,
        other_artist_user,
        managed_shipping_point_url,
    ):
        """Лейбл не управляет ПВЗ чужого артиста."""
        response = label_client.get(
            managed_shipping_point_url(
                other_artist_user.artist_profile,
            ),
        )

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_put_shipping_point_via_me_alias(
        self,
        artist_without_shipping_point_client,
        artist_without_shipping_point,
        artist_me_shipping_point_url,
    ):
        """Алиас me создаёт ПВЗ собственного профиля."""
        response = artist_without_shipping_point_client.put(
            artist_me_shipping_point_url,
            data={
                'point': {
                    'pvz_code': 'KGN12',
                    'city_code': '123',
                    'city': 'Курган',
                    'address': 'ул. Гоголя, 55',
                },
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.OK
        assert ArtistShippingPoint.objects.filter(
            artist=artist_without_shipping_point.artist_profile,
            pvz_code='KGN12',
        ).exists()

    def test_deleting_shipping_point_disables_shipping(
        self,
        artist_client,
        artist_user,
        managed_shipping_point_url,
    ):
        """Удаление ПВЗ автоматически выключает доставку СДЭК."""
        profile = artist_user.artist_profile
        shipping_point_id = profile.shipping_point.id

        settings, _ = ArtistStoreSettings.objects.update_or_create(
            artist=profile,
            defaults={
                'shipping_enabled': True,
            },
        )

        response = artist_client.delete(
            managed_shipping_point_url(profile),
        )

        assert response.status_code == HTTPStatus.NO_CONTENT
        assert not ArtistShippingPoint.objects.filter(
            pk=shipping_point_id,
        ).exists()

        settings.refresh_from_db()

        assert settings.shipping_enabled is False

    def test_cannot_enable_shipping_without_point(
        self,
        artist_without_shipping_point_client,
        artist_without_shipping_point,
        managed_shipping_point_url,
    ):
        """Нельзя включить СДЭК без настроенного ПВЗ."""
        profile = artist_without_shipping_point.artist_profile

        response = artist_without_shipping_point_client.put(
            managed_shipping_point_url(profile),
            data={
                'enabled': True,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert 'enabled' in response.data


class TestArtistDeliveryPermissions:
    """Тесты прав доступа к настройкам доставки."""

    def test_listener_cannot_access_pickup_points(
        self,
        listener_client,
        artist_user,
        managed_pickup_point_list_url,
    ):
        """Слушатель не получает доступ к настройкам доставки."""
        response = listener_client.get(
            managed_pickup_point_list_url(
                artist_user.artist_profile,
            ),
        )

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_anonymous_user_requires_authentication(
        self,
        api_client,
        artist_user,
        managed_shipping_point_url,
    ):
        """Анонимному пользователю требуется авторизация."""
        response = api_client.get(
            managed_shipping_point_url(
                artist_user.artist_profile,
            ),
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED
