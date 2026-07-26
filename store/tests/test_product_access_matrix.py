"""Комплексная проверка прав доступа и статусов публикации альбомов."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

ROLE_CLIENTS = {
    'anon': 'api_client',
    'user': 'auth_client',
    'artist': 'artist_client',
    'staff': 'staff_client',
}

ROUTE_NAMES = {
    'album': 'albums',
    'track': 'tracks',
    'merch': 'merch',
}


@pytest.fixture(params=['album', 'track', 'merch'])
def product_meta(request):
    """Фикстура, которая переключает контекст теста между типами продукта."""
    ptype = request.param
    route = ROUTE_NAMES[ptype]

    return {
        'type': ptype,
        'list_url': reverse(f'api:store:{route}-list'),
        'detail_url_name': f'api:store:{route}-detail',
    }


# fmt: off
@pytest.mark.parametrize(
    'role,visibility,action,can_see,expected_status,comment',
    [
        # =============== LIST (Видит только артист-владелец) ===============

        ('anon', 'public', 'list', False, 200, 'anon cannot see list'),
        ('anon', 'private', 'list', False, 200, 'anon cannot see list'),
        ('anon', 'link_only', 'list', False, 200, 'anon cannot see list'),

        ('user', 'public', 'list', False, 200, 'user cannot see list'),
        ('user', 'private', 'list', False, 200, 'user cannot see list'),
        ('user', 'link_only', 'list', False, 200, 'user cannot see list'),

        ('staff', 'public', 'list', False, 200, 'staff cannot see list'),
        ('staff', 'private', 'list', False, 200, 'staff cannot see list'),
        ('staff', 'link_only', 'list', False, 200, 'staff cannot see list'),

        ('artist', 'public', 'list', True, 200, 'owner can see public'),
        ('artist', 'private', 'list', True, 200, 'owner can see private'),
        ('artist', 'link_only', 'list', True, 200, 'owner can see link_only'),

        # =========== RETRIEVE (Доступен только артисту-владельцу) ===========

        ('anon', 'public', 'retrieve', False, 404, 'anon gets 404'),
        ('anon', 'private', 'retrieve', False, 404, 'anon gets 404'),
        ('anon', 'link_only', 'retrieve', False, 404, 'anon gets 404'),

        ('user', 'public', 'retrieve', False, 404, 'user gets 404'),
        ('user', 'private', 'retrieve', False, 404, 'user gets 404'),
        ('user', 'link_only', 'retrieve', False, 404, 'user gets 404'),

        ('staff', 'public', 'retrieve', False, 404, 'staff gets 404'),
        ('staff', 'private', 'retrieve', False, 404, 'staff gets 404'),
        ('staff', 'link_only', 'retrieve', False, 404, 'staff gets 404'),

        ('artist', 'public', 'retrieve', True, 200, 'owner can see public'),
        ('artist', 'private', 'retrieve', True, 200, 'owner can see private'),
        ('artist', 'link_only', 'retrieve', True, 200, 'owner can see link'),
    ],
)
# fmt: on
def test_product_visibility_matrix(
    role, visibility, action, can_see, expected_status, comment,
    request, variant_factory, product_meta, artist_user,
):
    """Тест изоляции продуктов: доступ только у артиста-владельца."""
    client = request.getfixturevalue(ROLE_CLIENTS[role])

    variant = variant_factory(
        product_type=product_meta['type'],
        visibility=visibility,
        artist=artist_user.artist_profile,
        created_by=artist_user,
    )
    obj = getattr(variant.product, product_meta['type'])

    if action == 'list':
        # ================= LIST =================
        response = client.get(product_meta['list_url'])
        assert response.status_code == expected_status, f'Failed on: {comment}'

        ids = [item['id'] for item in response.data['results']]
        assert (obj.id in ids) == can_see, f'Failed on: {comment}'
    else:
        # ================= RETRIEVE =================
        url = reverse(product_meta['detail_url_name'], args=[obj.id])
        response = client.get(url)
        assert response.status_code == expected_status, f'Failed on: {comment}'

        if can_see:
            assert response.data['id'] == obj.id


# fmt: off
@pytest.mark.parametrize(
    'role, is_published, is_active, expected_status, can_see_in_list, comment',
    [
        # ================= НЕ ОПУБЛИКОВАНО (Черновики) =================
        ('anon',   False, True,  404, False, 'anon cannot see unpublished'),
        ('user',   False, True,  404, False, 'user cannot see unpublished'),
        ('staff',  False, True,  404, False, 'staff cannot see unpublished'),
        ('artist', False, True,  200, True,  'owner can see their own draft'),

        # ================= НЕ АКТИВНО (Деактивировано) =================
        ('anon',   True,  False, 404, False, 'anon cannot see inactive'),
        ('user',   True,  False, 404, False, 'user cannot see inactive'),
        ('staff',  True,  False, 404, False, 'staff cannot see inactive'),
        ('artist', True,  False, 404, False, 'owner cannot see own inactive'),
    ],
)
# fmt: on
def test_product_status_logic(
    role, is_published, is_active, expected_status, can_see_in_list, comment,
    request, variant_factory, product_meta, artist_user,
):
    """Тест базовых флагов жизненного цикла: публикация и активность."""
    client = request.getfixturevalue(ROLE_CLIENTS[role])

    variant = variant_factory(
        product_type=product_meta['type'],
        visibility='public',
        is_published=is_published,
        is_active=is_active,
        artist=artist_user.artist_profile,
        created_by=artist_user,
    )
    obj = getattr(variant.product, product_meta['type'])

    # ================= LIST =================
    list_response = client.get(product_meta['list_url'])
    ids = [item['id'] for item in list_response.data['results']]
    assert (obj.id in ids) == can_see_in_list, f'Failed on: {comment}'

    # ================= RETRIEVE =================
    url = reverse(product_meta['detail_url_name'], args=[obj.id])
    response = client.get(url)
    assert response.status_code == expected_status, f'Failed on: {comment}'


# fmt: off
@pytest.mark.parametrize(
    'role, method, expected_status, comment',
    [
        # --- Не-владельцы не имеют доступа (404/401) ---
        ('anon',   'get',    404, 'anon gets 404'),
        ('user',   'get',    404, 'regular user gets 404'),
        ('staff',  'get',    404, 'staff gets 404'),

        ('anon',   'patch',  401, 'anon cannot edit'),
        ('user',   'patch',  404, 'regular user gets 404 on patch'),
        ('staff',  'patch',  404, 'staff gets 404 on patch'),

        ('user',   'delete', 404, 'regular user gets 404 on delete'),
        ('staff',  'delete', 404, 'staff gets 404 on delete'),

        # --- Артист-владелец ---
        ('artist', 'get',    200, 'owner can read'),
        ('artist', 'patch',  200, 'owner can edit'),
        ('artist', 'delete', 204, 'owner can delete'),
    ],
)
# fmt: on
def test_product_permissions_logic(
    role, method, expected_status, comment,
    request, variant_factory, product_meta, artist_user,
):
    """Тест прав доступа: изолированные операции владельца."""
    client = request.getfixturevalue(ROLE_CLIENTS[role])

    variant = variant_factory(
        product_type=product_meta['type'],
        visibility='public',
        artist=artist_user.artist_profile,
        created_by=artist_user,
    )
    obj = getattr(variant.product, product_meta['type'])

    url = reverse(product_meta['detail_url_name'], args=[obj.id])

    if method == 'get':
        response = client.get(url)
    elif method == 'patch':
        response = client.patch(url, data={'name': 'new name'}, format='json')
    elif method == 'delete':
        response = client.delete(url)

    assert response.status_code == expected_status, f'Failed on: {comment}'


@pytest.mark.parametrize(
    'role, expected_status, comment',
    [
        ('anon',   401, 'anon cannot create'),
        ('user',   403, 'regular user cannot create'),
        ('artist', 201, 'artist can create'),
        ('staff',  403, 'staff cannot create (if not artist)'),
    ],
)
def test_product_create_permission(
    role, expected_status, comment,
    request, product_meta, artist_user, variant_factory,
):
    """Тест прав на создание: только пользователь с профилем артиста."""
    if role == 'artist':
        client = request.getfixturevalue('auth_client')
        client.force_authenticate(user=artist_user)
    else:
        client = request.getfixturevalue(ROLE_CLIENTS[role])

    payload = {
        'name': f'New {product_meta["type"]}',
        'price': '100.00',
    }
    if product_meta['type'] == 'track':
        album = variant_factory(
            'album',
            artist=artist_user.artist_profile,
            created_by=artist_user,
        )
        payload.update({
            'album': album.id,
            'audio_file': SimpleUploadedFile(
                'test.mp3', b'a', content_type='audio/mpeg',
            ),
        })

    response = client.post(
        product_meta['list_url'], data=payload, format='multipart',
    )

    assert response.status_code == expected_status, f'Failed on: {comment}'
