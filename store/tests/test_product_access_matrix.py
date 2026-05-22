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
        # ================= LIST =================

        ('anon', 'public', 'list', True, 200, 'anon can public'),
        ('anon', 'private', 'list', False, 200, 'anon cannot private'),
        ('anon', 'link_only', 'list', False, 200, 'anon cannot link_only'),

        ('artist', 'public', 'list', True, 200, 'artist can public'),
        ('artist', 'private', 'list', True, 200, 'artist can own private'),
        ('artist', 'link_only', 'list', True, 200, 'artist can link_only'),

        ('user', 'public', 'list', True, 200, 'user can public'),
        ('user', 'private', 'list', False, 200, 'user cannot private'),
        ('user', 'link_only', 'list', False, 200, 'user cannot link_only'),

        ('staff', 'public', 'list', True, 200, 'staff full access'),
        ('staff', 'private', 'list', True, 200, 'staff full access'),
        ('staff', 'link_only', 'list', True, 200, 'staff full access'),

        # ================= RETRIEVE =================

        ('anon', 'public', 'retrieve', True, 200, 'anon can public'),
        ('anon', 'private', 'retrieve', False, 404, 'anon cannot private'),
        ('anon', 'link_only', 'retrieve', True, 200, 'anon can link_only'),

        ('artist', 'public', 'retrieve', True, 200, 'artist can public'),
        ('artist', 'private', 'retrieve', True, 200, 'artist can own private'),
        ('artist', 'link_only', 'retrieve', True, 200, 'artist can link_only'),

        ('user', 'public', 'retrieve', True, 200, 'user can public'),
        ('user', 'private', 'retrieve', False, 404, 'user cannot private'),
        ('user', 'link_only', 'retrieve', True, 200, 'user can link_only'),

        ('staff', 'public', 'retrieve', True, 200, 'staff full access'),
        ('staff', 'private', 'retrieve', True, 200, 'staff full access'),
        ('staff', 'link_only', 'retrieve', True, 200, 'staff full access'),
    ],
)
# fmt: on
def test_product_visibility_matrix(
    role, visibility, action, can_see, expected_status, comment,
    request, variant_factory, product_meta,
):
    """Тест доступа к продукту (roles × visibility × actions)."""
    client = request.getfixturevalue(ROLE_CLIENTS[role])

    variant = variant_factory(
        product_type=product_meta['type'],
        visibility=visibility,
    )
    obj = getattr(variant.product, product_meta['type'])

    if action == 'list':
        # ================= LIST =================
        response = client.get(product_meta['list_url'])

        ids = [item['id'] for item in response.data['results']]
        assert (obj.id in ids) == can_see, f'Failed on: {comment}'
    else:
        # ================= RETRIEVE =================
        url = reverse(product_meta['detail_url_name'], args=[obj.id])
        response = client.get(url)
        if can_see:
            assert response.data['id'] == obj.id
    assert response.status_code == expected_status, f'Failed on: {comment}'


# fmt: off
@pytest.mark.parametrize(
    'role, is_published, is_active, expected_status, can_see_in_list, comment',
    [
        # ================= НЕ ОПУБЛИКОВАНО (Черновики) =================
        ('anon',   False, True,  404, False, 'anon cannot see unpublished'),
        ('user',   False, True,  404, False,  'user cannot see unpublished'),
        ('artist', False, True,  200, True,  'owner can see their own draft'),
        ('staff',  False, True,  200, True,  'staff can see unpublished'),

        # ================= НЕ АКТИВНО (Деактивировано) =================
        ('anon',   True,  False, 404, False, 'anon cannot see inactive'),
        ('user',   True,  False, 404, False, 'user cannot see inactive'),
        ('artist', True, False, 404, False,  'owner cannot see own inactive'),
        ('staff',  True,  False, 200, True,  'staff can see inactive'),
    ],
)
# fmt: on
def test_product_status_logic(
    role, is_published, is_active, expected_status, can_see_in_list, comment,
    request, variant_factory, product_meta,
):
    """Тест базовых флагов жизненного цикла: публикация и активность."""
    client = request.getfixturevalue(ROLE_CLIENTS[role])

    variant = variant_factory(
        product_type=product_meta['type'],
        visibility='public',
        is_published=is_published,
        is_active=is_active,
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
        # --- Чтение (Safe Methods) ---
        ('anon',   'get',    200, 'anon can read public'),
        ('user',   'get',    200, 'regular user can read public'),
        ('artist', 'get',    200, 'owner can read public'),

        # --- Изменение (Unsafe Methods) ---
        ('anon',   'patch',  401, 'anon cannot edit'),
        ('user',   'patch',  403, 'regular user cannot edit'),
        ('artist', 'patch',  200, 'owner can edit'),
        ('staff',  'patch',  403, 'staff cannot edit too'),

        # --- Удаление ---
        ('user',   'delete', 403, 'regular user cannot delete'),
        ('artist', 'delete', 204, 'owner can delete'),
    ],
)
# fmt: on
def test_product_permissions_logic(
    role, method, expected_status, comment,
    request, variant_factory, product_meta,
):
    """Тест прав доступа: Role × Method (Owner or Read-Only)."""
    client = request.getfixturevalue(ROLE_CLIENTS[role])

    variant = variant_factory(
        product_type=product_meta['type'],
        visibility='public',
    )
    obj = getattr(variant.product, product_meta['type'])

    url = reverse(product_meta['detail_url_name'], args=[obj.id])

    if method == 'get':
        response = client.get(url)
    elif method == 'patch':
        response = client.patch(url, data={'name': 'new name'})
    elif method == 'delete':
        response = client.delete(url)

    assert response.status_code == expected_status, f'Failed on: {comment}'


@pytest.mark.parametrize(
    'role, expected_status, comment',
    [
        ('anon',   401, 'anon cannot create'),
        ('user',   403, 'regular user cannot create'),
        ('artist', 201, 'artist can create'),
        ('staff',  403, 'staff cannot create (если не артист)'),
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
        album = variant_factory('album')
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
