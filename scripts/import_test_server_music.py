#!/usr/bin/env python3
# ruff: noqa: D103
"""Импорт тестового контента через публичный API.

Скрипт создает и переиспользует:
- жанры;
- типы мерча;
- артистов;
- обложки артистов и альбомов;
- альбомы;
- треки;
- мерч с вариантами и изображениями.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

from scripts.test_content.constants import AUDIO_FIXTURE
from scripts.test_content.images import png_file_tuple
from scripts.test_content.matching import (
    marker,
    marker_id_by_description,
    match_genres,
    match_merch_kinds,
    normalize_username,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Импорт тестового контента через API.',
    )
    parser.add_argument(
        '--base-url',
        required=True,
        help='Базовый URL API, например: https://example.com/api/v1',
    )
    parser.add_argument(
        '--password',
        default='TestPass123!@#',
        help='Пароль для всех fixture-аккаунтов артистов.',
    )
    parser.add_argument(
        '--payload',
        default=str(
            Path(__file__).resolve().parent
            / 'data'
            / 'test_server_friendly_indie_payload.json',
        ),
        help='Путь к JSON-датасету импорта.',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=20,
        help='Таймаут HTTP-запросов в секундах.',
    )
    parser.add_argument(
        '--request-delay',
        type=float,
        default=0.0,
        help='Пауза после успешного изменяющего запроса, секунды.',
    )
    return parser.parse_args()


def api_url(base_url: str, path: str) -> str:
    return f'{base_url.rstrip("/")}/{path.lstrip("/")}'


def throttle_wait_seconds(response: requests.Response, attempt: int) -> int:
    """Определяет паузу перед повтором после 429."""
    retry_after = response.headers.get('Retry-After')
    if retry_after and retry_after.isdigit():
        return int(retry_after)

    try:
        detail = str(response.json().get('detail', ''))
    except ValueError:
        detail = response.text

    marker = 'Expected available in '
    if marker in detail:
        tail = detail.split(marker, 1)[1]
        seconds = tail.split(' seconds', 1)[0]
        if seconds.isdigit():
            return int(seconds) + 1

    return min(2**attempt, 10)


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    timeout: int,
    max_attempts: int = 8,
    request_delay: float = 0.0,
    **kwargs,
) -> requests.Response:
    """HTTP-запрос с retry на 429 Too Many Requests."""
    response = None

    for attempt in range(max_attempts):
        response = session.request(method, url, timeout=timeout, **kwargs)

        if response.status_code != 429:
            if request_delay > 0 and method.upper() in {
                'POST',
                'PATCH',
                'PUT',
                'DELETE',
            }:
                time.sleep(request_delay)
            return response

        sleep_seconds = throttle_wait_seconds(response, attempt)
        time.sleep(sleep_seconds)

    return response


def ensure_response_ok(response: requests.Response, context: str) -> dict:
    if response.ok:
        if response.text.strip():
            return response.json()
        return {}
    raise RuntimeError(
        f'{context} failed: HTTP {response.status_code} {response.text}',
    )


def extract_results(data: dict | list) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get('results'), list):
        return data['results']
    return []


def paginated_get(
    session: requests.Session,
    base_url: str,
    path: str,
    timeout: int,
    token: str | None = None,
) -> list[dict]:
    items: list[dict] = []
    limit = 200
    offset = 0
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    while True:
        separator = '&' if '?' in path else '?'
        response = request_with_retry(
            session,
            'GET',
            api_url(
                base_url,
                f'{path}{separator}limit={limit}&offset={offset}',
            ),
            headers=headers,
            timeout=timeout,
        )
        payload = ensure_response_ok(response, f'GET {path}')
        if isinstance(payload, list):
            items.extend(payload)
            break
        batch = payload.get('results', [])
        if not isinstance(batch, list):
            raise RuntimeError(f'Unexpected payload for {path}: {payload}')
        items.extend(batch)
        if not payload.get('next'):
            break
        offset += limit
    return items


def register_or_login_artist(
    session: requests.Session,
    base_url: str,
    artist: dict,
    password: str,
    timeout: int,
    request_delay: float,
) -> str:
    username_seed = normalize_username(artist['slug'])
    username = f'fixture-{username_seed}'
    email = f'{username_seed}@fixtures.zvuchno.local'
    digest = hashlib.sha256(username_seed.encode('utf-8')).hexdigest()
    phone_suffix = f'{int(digest[:12], 16) % 10_000_000_000:010d}'
    phone = f'+7{phone_suffix}'

    register_response = request_with_retry(
        session,
        'POST',
        api_url(base_url, '/auth/register/artist/'),
        json={
            'username': username,
            'email': email,
            'phone': phone,
            'name': artist['name'],
            'password': password,
        },
        timeout=timeout,
        request_delay=request_delay,
    )
    if register_response.status_code not in (200, 201, 400):
        raise RuntimeError(
            f"artist register '{artist['name']}' failed: "
            f'HTTP {register_response.status_code} {register_response.text}',
        )

    token_response = request_with_retry(
        session,
        'POST',
        api_url(base_url, '/auth/token/create/'),
        json={'email': email, 'password': password},
        timeout=timeout,
        request_delay=request_delay,
    )
    token_data = ensure_response_ok(
        token_response,
        f"token create for '{artist['name']}'",
    )
    access_token = token_data.get('access')
    if not access_token:
        raise RuntimeError(
            f"token create for '{artist['name']}' failed: no access token",
        )
    return access_token


def update_artist_profile(
    session: requests.Session,
    base_url: str,
    artist: dict,
    token: str,
    timeout: int,
    request_delay: float,
) -> None:
    response = request_with_retry(
        session,
        'PATCH',
        api_url(base_url, '/artists/me/'),
        headers={'Authorization': f'Bearer {token}'},
        json={
            'name': artist['name'],
            'city': artist.get('city', ''),
            'description': (
                f'{artist["name"]} ({artist.get("genre_slug", "music")}) '
                'imported as test fixture via API'
            ),
            'url': f'https://fixtures.zvuchno.local/artists/{artist["slug"]}',
        },
        timeout=timeout,
        request_delay=request_delay,
    )
    ensure_response_ok(response, f"update artist profile '{artist['name']}'")

    current_response = request_with_retry(
        session,
        'GET',
        api_url(base_url, '/artists/me/'),
        headers={'Authorization': f'Bearer {token}'},
        timeout=timeout,
    )
    current = ensure_response_ok(
        current_response,
        f"get artist profile '{artist['name']}'",
    )
    if current.get('cover'):
        return

    cover_response = request_with_retry(
        session,
        'PATCH',
        api_url(base_url, '/artists/me/cover/'),
        headers={'Authorization': f'Bearer {token}'},
        files={
            'cover': png_file_tuple(
                artist['slug'],
                'artist',
                f'{artist["slug"]}-artist.png',
            ),
        },
        timeout=timeout,
        request_delay=request_delay,
    )
    ensure_response_ok(
        cover_response,
        f"upload artist cover '{artist['name']}'",
    )


def create_album(
    session: requests.Session,
    base_url: str,
    artist: dict,
    album: dict,
    genre_id: int,
    album_marker: str,
    token: str,
    timeout: int,
    request_delay: float,
) -> int:
    response = request_with_retry(
        session,
        'POST',
        api_url(base_url, '/store/albums/'),
        headers={'Authorization': f'Bearer {token}'},
        data={
            'name': album['name'],
            'is_single': 'false',
            'release_date': album['release_date'],
            'genre': str(genre_id),
            'price': str(album.get('price', '199.00')),
            'description': (
                f'{album_marker} {artist["name"]} / {album["name"]} / '
                'test import fixture'
            ),
            'allow_overpay': str(album.get('allow_overpay', False)).lower(),
            'visibility': album.get('visibility', 'public'),
            'is_published': str(album.get('is_published', True)).lower(),
        },
        files={
            'cover_image': png_file_tuple(
                f'{artist["slug"]}:{album["name"]}',
                'album',
                f'{artist["slug"]}-{normalize_username(album["name"])}.png',
            ),
        },
        timeout=timeout,
        request_delay=request_delay,
    )
    data = ensure_response_ok(response, f"create album '{album['name']}'")
    return data['id']


def create_track(
    session: requests.Session,
    base_url: str,
    track_payload: dict,
    audio_path: Path,
    token: str,
    timeout: int,
    request_delay: float,
) -> None:
    with audio_path.open('rb') as audio_file:
        response = request_with_retry(
            session,
            'POST',
            api_url(base_url, '/store/tracks/'),
            headers={'Authorization': f'Bearer {token}'},
            data={
                'name': track_payload['name'],
                'album': str(track_payload['album']),
                'position': str(track_payload['position']),
                'price': str(track_payload['price']),
                'allow_overpay': 'false',
                'description': track_payload['description'],
            },
            files={'audio_file': (audio_path.name, audio_file, 'audio/mpeg')},
            timeout=timeout,
            request_delay=request_delay,
        )
    ensure_response_ok(response, f"create track '{track_payload['name']}'")


def format_merch(raw: dict, artist: dict) -> dict:
    result = dict(raw)
    for key in ('name', 'description', 'property_name'):
        if isinstance(result.get(key), str):
            result[key] = result[key].format(
                artist=artist['name'],
                artist_slug=artist['slug'],
            )
    return result


def create_merch(
    session: requests.Session,
    base_url: str,
    merch: dict,
    merch_marker: str,
    kind_id: int,
    album_id: int | None,
    token: str,
    timeout: int,
    request_delay: float,
) -> int:
    data: dict[str, Any] = {
        'name': merch['name'],
        'kind': kind_id,
        'price': str(merch.get('price', '999.00')),
        'description': f'{merch_marker} {merch.get("description", "")}',
        'allow_overpay': merch.get('allow_overpay', False),
        'visibility': merch.get('visibility', 'public'),
        'is_published': merch.get('is_published', True),
    }
    if album_id is not None:
        data['album'] = album_id
    if 'property_name' in merch:
        data['property_name'] = merch.get('property_name', '')
    if merch.get('variants'):
        data['variants'] = merch['variants']
    else:
        data['stock'] = merch.get('stock', 10)

    response = request_with_retry(
        session,
        'POST',
        api_url(base_url, '/store/merch/'),
        headers={'Authorization': f'Bearer {token}'},
        json=data,
        timeout=timeout,
        request_delay=request_delay,
    )
    created = ensure_response_ok(response, f"create merch '{merch['name']}'")
    return created['id']


def ensure_merch_image(
    session: requests.Session,
    base_url: str,
    merch_id: int,
    merch: dict,
    token: str,
    timeout: int,
    request_delay: float,
) -> bool:
    detail_response = request_with_retry(
        session,
        'GET',
        api_url(base_url, f'/store/merch/{merch_id}/'),
        headers={'Authorization': f'Bearer {token}'},
        timeout=timeout,
    )
    detail = ensure_response_ok(detail_response, f'get merch {merch_id}')
    if detail.get('main_image') or detail.get('images_merch'):
        return False

    response = request_with_retry(
        session,
        'POST',
        api_url(base_url, f'/store/merch/{merch_id}/images/'),
        headers={'Authorization': f'Bearer {token}'},
        data={'is_main': 'true'},
        files={
            'image': png_file_tuple(
                ':'.join(
                    str(part)
                    for part in (
                        merch.get('artist_slug'),
                        merch.get('album_seed'),
                        merch.get('name'),
                        merch_id,
                    )
                    if part
                ),
                merch.get('kind_slug', 'merch'),
                f'merch-{merch_id}.png',
            ),
        },
        timeout=timeout,
        request_delay=request_delay,
    )
    ensure_response_ok(response, f"upload merch image '{merch.get('name')}'")
    return True


def main() -> int:  # noqa: C901
    args = parse_args()
    payload_path = Path(args.payload)
    if not payload_path.exists():
        raise FileNotFoundError(f'Payload file not found: {payload_path}')

    data = json.loads(payload_path.read_text(encoding='utf-8'))
    session = requests.Session()
    timeout = args.timeout
    request_delay = args.request_delay

    genres_by_slug = match_genres(
        paginated_get(
            session,
            args.base_url,
            '/store/genres/',
            timeout,
        ),
        data.get('genres', []),
    )

    with tempfile.NamedTemporaryFile(
        mode='wb',
        suffix='.mp3',
        delete=False,
    ) as audio_tmp:
        audio_tmp.write(AUDIO_FIXTURE)
        audio_path = Path(audio_tmp.name)

    counters = {
        'artists_seen': 0,
        'albums_created': 0,
        'tracks_created': 0,
        'merch_created': 0,
        'merch_images_created': 0,
        'merch_skipped': 0,
    }
    merch_kinds_by_slug = match_merch_kinds(
        paginated_get(
            session,
            args.base_url,
            '/store/merch-kinds/',
            timeout,
        ),
    )
    merch_templates = data.get('merch_templates', [])

    try:
        for artist in data.get('artists', []):
            token = register_or_login_artist(
                session=session,
                base_url=args.base_url,
                artist=artist,
                password=args.password,
                timeout=timeout,
                request_delay=request_delay,
            )
            counters['artists_seen'] += 1
            update_artist_profile(
                session=session,
                base_url=args.base_url,
                artist=artist,
                token=token,
                timeout=timeout,
                request_delay=request_delay,
            )
            existing_albums = paginated_get(
                session,
                args.base_url,
                '/store/albums/',
                timeout,
                token=token,
            )
            album_id_by_marker = marker_id_by_description(
                existing_albums,
                'album',
            )
            album_ids_by_index: dict[int, int] = {}

            for album_index, album in enumerate(
                artist.get('albums', []),
                start=1,
            ):
                album_marker = marker('album', artist['slug'], album_index)
                album_id = album_id_by_marker.get(album_marker)
                if album_id is None:
                    album_id = create_album(
                        session=session,
                        base_url=args.base_url,
                        artist=artist,
                        album=album,
                        genre_id=genres_by_slug[album['genre_slug']],
                        album_marker=album_marker,
                        token=token,
                        timeout=timeout,
                        request_delay=request_delay,
                    )
                    counters['albums_created'] += 1
                    album_id_by_marker[album_marker] = album_id
                album_ids_by_index[album_index] = album_id

            existing_tracks = paginated_get(
                session,
                args.base_url,
                '/store/tracks/',
                timeout,
                token=token,
            )
            track_keys = {
                (track.get('album'), track.get('position'), track.get('name'))
                for track in existing_tracks
                if isinstance(track, dict)
            }
            for album_index, album in enumerate(
                artist.get('albums', []),
                start=1,
            ):
                album_id = album_ids_by_index[album_index]
                for position, track_name in enumerate(
                    album.get('tracks', []),
                    start=1,
                ):
                    track_key = (album_id, position, track_name)
                    if track_key in track_keys:
                        continue
                    create_track(
                        session=session,
                        base_url=args.base_url,
                        token=token,
                        timeout=timeout,
                        request_delay=request_delay,
                        audio_path=audio_path,
                        track_payload={
                            'name': track_name,
                            'album': album_id,
                            'position': position,
                            'price': album.get('track_price', '49.00'),
                            'description': (
                                f'{artist["name"]} / '
                                f'{album["name"]} / {track_name}'
                            ),
                        },
                    )
                    counters['tracks_created'] += 1
                    track_keys.add(track_key)

            existing_merch = paginated_get(
                session,
                args.base_url,
                '/store/merch/',
                timeout,
                token=token,
            )
            merch_id_by_marker = marker_id_by_description(
                existing_merch,
                'merch',
            )
            merch_payloads = [
                format_merch(item, artist)
                for item in [*merch_templates, *artist.get('merch', [])]
            ]
            for merch_index, merch in enumerate(merch_payloads, start=1):
                kind_slug = merch['kind_slug']
                kind_id = merch_kinds_by_slug.get(kind_slug)
                if kind_id is None:
                    counters['merch_skipped'] += 1
                    continue
                merch_marker = marker(
                    'merch',
                    artist['slug'],
                    kind_slug,
                    merch_index,
                )
                merch_id = merch_id_by_marker.get(merch_marker)
                album_id = None
                if merch.get('album_index'):
                    album_id = album_ids_by_index.get(
                        int(merch['album_index']),
                    )
                if merch_id is None:
                    merch_id = create_merch(
                        session=session,
                        base_url=args.base_url,
                        merch=merch,
                        merch_marker=merch_marker,
                        kind_id=kind_id,
                        album_id=album_id,
                        token=token,
                        timeout=timeout,
                        request_delay=request_delay,
                    )
                    counters['merch_created'] += 1
                    merch_id_by_marker[merch_marker] = merch_id
                image_created = ensure_merch_image(
                    session=session,
                    base_url=args.base_url,
                    merch_id=merch_id,
                    merch={
                        **merch,
                        'kind_slug': kind_slug,
                        'artist_slug': artist['slug'],
                        'album_seed': album_id,
                    },
                    token=token,
                    timeout=timeout,
                    request_delay=request_delay,
                )
                if image_created:
                    counters['merch_images_created'] += 1
    finally:
        audio_path.unlink(missing_ok=True)

    print(
        'Import completed: '
        f'artists_seen={counters["artists_seen"]}, '
        f'albums_created={counters["albums_created"]}, '
        f'tracks_created={counters["tracks_created"]}, '
        f'merch_created={counters["merch_created"]}, '
        f'merch_images_created={counters["merch_images_created"]}, '
        f'merch_skipped={counters["merch_skipped"]}, '
        f'genres_total={len(genres_by_slug)}, '
        f'merch_kinds_matched={len(merch_kinds_by_slug)}',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
