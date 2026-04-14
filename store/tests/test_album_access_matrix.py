"""Комплексная проверка прав доступа и статусов публикации альбомов."""

import pytest
from django.urls import reverse

ROLE_CLIENTS = {
    'anon': 'api_client',
    'user': 'auth_client',
    'other': 'other_client',
    'staff': 'staff_client',
}


# fmt: off
@pytest.mark.parametrize(
    'role,visibility,action,can_see,expected_status,comment',
    [
        # ================= LIST =================

        ('anon', 'public', 'list', True, 200, 'anon can public'),
        ('anon', 'private', 'list', False, 200, 'anon cannot private'),
        ('anon', 'link_only', 'list', False, 200, 'anon cannot link_only'),

        ('user', 'public', 'list', True, 200, 'user can public'),
        ('user', 'private', 'list', True, 200, 'user can own private'),
        ('user', 'link_only', 'list', True, 200, 'user can link_only'),

        ('other', 'public', 'list', True, 200, 'other can public'),
        ('other', 'private', 'list', False, 200, 'other cannot private'),
        ('other', 'link_only', 'list', False, 200, 'other cannot link_only'),

        ('staff', 'public', 'list', True, 200, 'staff full access'),
        ('staff', 'private', 'list', True, 200, 'staff full access'),
        ('staff', 'link_only', 'list', True, 200, 'staff full access'),

        # ================= RETRIEVE =================

        ('anon', 'public', 'retrieve', True, 200, 'anon can public'),
        ('anon', 'private', 'retrieve', False, 404, 'anon cannot private'),
        ('anon', 'link_only', 'retrieve', True, 200, 'anon can link_only'),

        ('user', 'public', 'retrieve', True, 200, 'user can public'),
        ('user', 'private', 'retrieve', True, 200, 'user can own private'),
        ('user', 'link_only', 'retrieve', True, 200, 'user can link_only'),

        ('other', 'public', 'retrieve', True, 200, 'other can public'),
        ('other', 'private', 'retrieve', False, 404, 'other cannot private'),
        ('other', 'link_only', 'retrieve', True, 200, 'other can link_only'),

        ('staff', 'public', 'retrieve', True, 200, 'staff full access'),
        ('staff', 'private', 'retrieve', True, 200, 'staff full access'),
        ('staff', 'link_only', 'retrieve', True, 200, 'staff full access'),
    ],
)
# fmt: on
def test_album_visibility_matrix(
    role,
    visibility,
    action,
    can_see,
    expected_status,
    comment,
    request,
    variant_factory,
    album_list_url,
):
    """Тест доступа к альбомам (roles × visibility × actions)."""
    client = request.getfixturevalue(ROLE_CLIENTS[role])

    variant = variant_factory(
        product_type='album',
        visibility=visibility,
    )

    album_id = variant.product.album.id

    # ================= LIST =================
    if action == 'list':
        response = client.get(album_list_url)

        assert response.status_code == expected_status, comment

        ids = [item['id'] for item in response.data['results']]
        assert (album_id in ids) == can_see, comment
        return

    # ================= RETRIEVE =================
    url = reverse('api:store:albums-detail', args=[album_id])
    response = client.get(url)

    assert response.status_code == expected_status, comment

    if can_see:
        assert response.data['id'] == album_id


# fmt: off
@pytest.mark.parametrize(
    'role, is_published, is_active, expected_status, can_see_in_list, comment',
    [
        # ================= НЕ ОПУБЛИКОВАНО (Черновики) =================
        ('anon',  False, True,  404, False, 'anon cannot see unpublished'),
        ('other', False, True,  404, False, 'other cannot see unpublished'),
        ('user',  False, True,  200, True,  'owner can see their own draft'),
        ('staff', False, True,  200, True,  'staff can see unpublished'),

        # ================= НЕ АКТИВНО (Деактивировано) =================
        ('anon',  True,  False, 404, False, 'anon cannot see inactive'),
        ('other', True,  False, 404, False, 'other cannot see inactive'),
        ('user',  True,  False, 404, False, 'owner cannot see own inactive'),
        ('staff', True,  False, 200, True,  'staff can see inactive'),
    ],
)
# fmt: on
def test_album_status_logic(
    role, is_published, is_active, expected_status, can_see_in_list, comment,
    request, variant_factory, album_list_url,
):
    """Тест базовых флагов жизненного цикла: публикация и активность."""
    client = request.getfixturevalue(ROLE_CLIENTS[role])

    variant = variant_factory(
        product_type='album',
        visibility='public',
        is_published=is_published,
        is_active=is_active,
    )
    album_id = variant.product.album.id

    # ================= LIST =================
    list_response = client.get(album_list_url)
    ids = [item['id'] for item in list_response.data['results']]
    assert (album_id in ids) == can_see_in_list, f'Failed on: {comment}'

    # ================= RETRIEVE =================
    url = reverse('api:store:albums-detail', args=[album_id])
    response = client.get(url)
    assert response.status_code == expected_status, f'Failed on: {comment}'
