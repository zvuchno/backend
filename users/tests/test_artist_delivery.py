"""Тесты API настроек доставки управляемых профилей."""

from datetime import date
from http import HTTPStatus

import pytest

from users.models import ArtistPickupPoint, ArtistShippingPoint

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
                'address': 'г. Курган, ул. Ленина, 10',
                'pickup_date': '2026-08-15',
                'is_active': True,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        pickup_point = ArtistPickupPoint.objects.get(
            artist=profile,
        )

        assert pickup_point.address == 'г. Курган, ул. Ленина, 10'
        assert pickup_point.pickup_date == date(2026, 8, 15)
        assert pickup_point.is_active is True
        assert response.data == {
            'id': pickup_point.id,
            'address': 'г. Курган, ул. Ленина, 10',
            'pickup_date': '2026-08-15',
            'is_active': True,
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

        results = response.data

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
                'address': 'Пункт управляемого артиста',
                'pickup_date': '2026-08-20',
                'is_active': True,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        pickup_point = ArtistPickupPoint.objects.get(
            artist=label_created_artist,
        )

        assert pickup_point.address == 'Пункт управляемого артиста'
        assert pickup_point.pickup_date == date(2026, 8, 20)
        assert pickup_point.is_active is True

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
                'address': 'Пункт подключённого артиста',
                'pickup_date': '2026-08-21',
                'is_active': True,
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED
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
        data = {
            'address': 'Одинаковый адрес',
            'pickup_date': '2026-08-15',
            'is_active': True,
        }

        first_response = artist_client.post(
            managed_pickup_point_list_url(profile),
            data=data,
            format='json',
        )
        second_response = artist_client.post(
            managed_pickup_point_list_url(profile),
            data=data,
            format='json',
        )

        assert first_response.status_code == HTTPStatus.CREATED
        assert second_response.status_code == HTTPStatus.BAD_REQUEST

    def test_different_artists_can_have_same_active_pickup_point(
        self,
        artist_client,
        artist_user,
        other_artist_user,
        managed_pickup_point_list_url,
    ):
        """Разным артистам разрешены одинаковые точки самовывоза."""
        data = {
            'address': 'Общий концертный зал',
            'pickup_date': '2026-08-15',
            'is_active': True,
        }

        ArtistPickupPoint.objects.create(
            artist=other_artist_user.artist_profile,
            **data,
        )

        response = artist_client.post(
            managed_pickup_point_list_url(
                artist_user.artist_profile,
            ),
            data=data,
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED


class TestArtistShippingPointAPI:
    """Тесты управления ПВЗ отправления."""

    def test_get_returns_null_when_shipping_point_does_not_exist(
        self,
        artist_without_shipping_point_client,
        artist_without_shipping_point,
        managed_shipping_point_url,
    ):
        """При отсутствии ПВЗ API возвращает null."""
        response = artist_without_shipping_point_client.get(
            managed_shipping_point_url(
                artist_without_shipping_point.artist_profile,
            ),
        )

        assert response.status_code == HTTPStatus.OK
        assert response.data is None

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
                'pvz_code': 'KGN12',
                'city_code': '123',
                'city': 'Курган',
                'address': 'ул. Гоголя, 55',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED

        shipping_point = ArtistShippingPoint.objects.get(
            artist=profile,
        )

        assert shipping_point.pvz_code == 'KGN12'
        assert shipping_point.city_code == '123'
        assert shipping_point.city == 'Курган'
        assert shipping_point.address == 'ул. Гоголя, 55'
        assert response.data == {
            'pvz_code': 'KGN12',
            'city_code': '123',
            'city': 'Курган',
            'address': 'ул. Гоголя, 55',
        }

    def test_repeated_put_updates_existing_shipping_point(
        self,
        artist_client,
        artist_user,
        managed_shipping_point_url,
    ):
        """Повторный PUT обновляет существующий ПВЗ."""
        profile = artist_user.artist_profile
        shipping_point = profile.shipping_point

        response = artist_client.put(
            managed_shipping_point_url(profile),
            data={
                'pvz_code': 'NEW2',
                'city_code': '456',
                'city': 'Тюмень',
                'address': 'Новый адрес',
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

        assert shipping_point.pvz_code == 'NEW2'
        assert shipping_point.city_code == '456'
        assert shipping_point.city == 'Тюмень'
        assert shipping_point.address == 'Новый адрес'

    def test_get_returns_existing_shipping_point(
        self,
        artist_client,
        artist_user,
        managed_shipping_point_url,
    ):
        """Артист получает сохранённый ПВЗ отправления."""
        profile = artist_user.artist_profile
        shipping_point = profile.shipping_point

        response = artist_client.get(
            managed_shipping_point_url(profile),
        )

        assert response.status_code == HTTPStatus.OK
        assert response.data == {
            'pvz_code': shipping_point.pvz_code,
            'city_code': shipping_point.city_code,
            'city': shipping_point.city,
            'address': shipping_point.address,
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
        """Лейбл настраивает ПВЗ управляемого артиста."""
        response = label_client.put(
            managed_shipping_point_url(label_created_artist),
            data={
                'pvz_code': 'MSK100',
                'city_code': '44',
                'city': 'Москва',
                'address': 'ул. Тестовая, 1',
            },
            format='json',
        )

        assert response.status_code == HTTPStatus.CREATED
        assert ArtistShippingPoint.objects.filter(
            artist=label_created_artist,
            pvz_code='MSK100',
        ).exists()

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
