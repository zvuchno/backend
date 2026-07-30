"""Тесты прав доступа к API управления контентом артиста."""

import pytest
from django.urls import reverse

ROUTE_NAMES = {
    'album': 'albums',
    'track': 'tracks',
    'merch': 'merch',
}


@pytest.fixture(params=['album', 'track', 'merch'])
def product_meta(request):
    """Возвращает настройки API для типов контента."""
    product_type = request.param
    route = ROUTE_NAMES[product_type]

    return {
        'type': product_type,
        'list_url': reverse(f'api:store:{route}-list'),
        'detail_url_name': f'api:store:{route}-detail',
    }


def get_product_object(variant, product_type):
    """Возвращает сущность контента из Product."""
    return getattr(variant.product, product_type)


# ===========================================================================
#  Защита от неавторизованных и обычных пользователей (Аноним / Listener)
# ===========================================================================
@pytest.mark.django_db
@pytest.mark.parametrize(
    'client_fixture, expected_status',
    [
        ('api_client', 401),
        ('auth_client', 403),
    ],
)
def test_unauthorized_access_denied(
    client_fixture,
    expected_status,
    request,
    product_meta,
):
    """Посторонним (анонимы и слушатели) запрещён доступ к ручкам контента."""
    client = request.getfixturevalue(client_fixture)

    response_list = client.get(product_meta['list_url'])
    assert response_list.status_code == expected_status

    response_create = client.post(
        product_meta['list_url'],
        data={},
        format='json',
    )
    assert response_create.status_code == expected_status


# ===========================================================================
#  Изоляция данных между разными артистами
# ===========================================================================
def test_other_artist_cannot_access_or_modify_content(
    other_artist_client,
    variant_factory,
    product_meta,
    artist_user,
):
    """Чужой артист не видит чужие сущности в списке и не имеет доступа."""
    variant = variant_factory(
        product_type=product_meta['type'],
        artist=artist_user.artist_profile,
        created_by=artist_user,
    )
    obj = get_product_object(variant, product_meta['type'])
    detail_url = reverse(product_meta['detail_url_name'], args=[obj.id])

    # Не видит в списке кабинетных продуктов
    list_response = other_artist_client.get(product_meta['list_url'])
    assert list_response.status_code == 200
    ids_in_list = [item['id'] for item in list_response.data['results']]
    assert obj.id not in ids_in_list

    # 404 при попытке получить или изменить детальную карточку
    assert other_artist_client.get(detail_url).status_code == 404
    assert (
        other_artist_client.patch(
            detail_url,
            data={'name': 'Hack'},
            format='json',
        ).status_code
        == 404
    )
    assert other_artist_client.delete(detail_url).status_code == 404


# ===========================================================================
#  Полный доступ владельца (CRUD операции артиста)
# ===========================================================================
@pytest.mark.parametrize(
    'method, data, expected_status',
    [
        ('get', None, 200),
        ('patch', {'name': 'Updated Title'}, 200),
        ('delete', None, 204),
    ],
)
def test_artist_owner_full_crud_access(
    method,
    data,
    expected_status,
    artist_client,
    variant_factory,
    product_meta,
    artist_user,
):
    """Артист может читать, редактировать и удалять свой контент."""
    variant = variant_factory(
        product_type=product_meta['type'],
        artist=artist_user.artist_profile,
        created_by=artist_user,
    )
    obj = get_product_object(variant, product_meta['type'])
    url = reverse(product_meta['detail_url_name'], args=[obj.id])

    request_func = getattr(artist_client, method)
    kwargs = {'format': 'json'} if data else {}
    if data:
        kwargs['data'] = data

    response = request_func(url, **kwargs)
    assert response.status_code == expected_status
