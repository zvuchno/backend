#!/usr/bin/env python3
"""Импорт тестовых музыкальных данных через API.

Скрипт создает:
- жанры;
- артистов (регистрация + логин);
- альбомы;
- треки (с multipart-загрузкой аудиофайла).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import requests


def parse_args() -> argparse.Namespace:
    """Todo: docstring."""
    parser = argparse.ArgumentParser(
        description='Импорт тестового музыкального набора через API.',
    )
    parser.add_argument(
        '--base-url',
        required=True,
        help='Базовый URL API, например: https://example.com/api/v1',
    )
    parser.add_argument(
        '--password',
        default='TestPass123!@#',
        help='Пароль для всех создаваемых артистов '
        '(по умолчанию безопасный тестовый).',
    )
    parser.add_argument(
        '--payload',
        default=str(
            Path(__file__).resolve().parent
            / 'data'
            / 'test_server_music_payload.json',
        ),
        help='Путь к JSON-датасету импорта.',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=20,
        help='Таймаут HTTP-запросов в секундах.',
    )
    return parser.parse_args()


def api_url(base_url: str, path: str) -> str:
    """Todo: docstring."""
    return f'{base_url.rstrip("/")}/{path.lstrip("/")}'


def ensure_response_ok(response: requests.Response, context: str) -> dict:
    """Todo: docstring."""
    if response.ok:
        if response.text.strip():
            return response.json()
        return {}
    raise RuntimeError(
        f'{context} failed: HTTP {response.status_code} {response.text}',
    )


def extract_results(data: dict | list) -> list:
    """Todo: docstring."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return []


def normalize_username(source: str) -> str:
    """Todo: docstring."""
    return ''.join(
        char if char.isalnum() else '-' for char in source.lower()
    ).strip('-')


def register_or_login_artist(
    session: requests.Session,
    base_url: str,
    artist: dict,
    password: str,
    timeout: int,
) -> str:
    """Todo: docstring."""
    username_seed = normalize_username(artist['slug'])
    username = f'fixture-{username_seed}'
    email = f'{username_seed}@fixtures.zvuchno.local'
    digest = hashlib.sha256(username_seed.encode('utf-8')).hexdigest()
    phone_suffix = f'{int(digest[:12], 16) % 10_000_000_000:010d}'
    phone = f'+7{phone_suffix}'

    register_payload = {
        'username': username,
        'email': email,
        'phone': phone,
        'name': artist['name'],
        'password': password,
    }
    register_response = session.post(
        api_url(base_url, '/auth/register/artist/'),
        json=register_payload,
        timeout=timeout,
    )
    if register_response.status_code not in (200, 201, 400):
        raise RuntimeError(
            f"artist register '{artist['name']}' failed: "
            f'HTTP {register_response.status_code} {register_response.text}',
        )

    token_response = session.post(
        api_url(base_url, '/auth/token/create/'),
        json={'email': email, 'password': password},
        timeout=timeout,
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
) -> None:
    """Todo: docstring."""
    response = session.patch(
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
    )
    ensure_response_ok(response, f"update artist profile '{artist['name']}'")


def ensure_genres(
    session: requests.Session,
    base_url: str,
    genres_payload: list[dict],
    timeout: int,
) -> dict[str, int]:
    """Todo: docstring."""
    list_response = session.get(
        api_url(base_url, '/store/genres/'),
        timeout=timeout,
    )
    list_data = ensure_response_ok(list_response, 'list genres')
    genre_items = extract_results(list_data)
    genres_by_slug = {
        item['slug']: item['id']
        for item in genre_items
        if isinstance(item, dict) and 'slug' in item and 'id' in item
    }

    for genre in genres_payload:
        if genre['slug'] in genres_by_slug:
            continue
        create_response = session.post(
            api_url(base_url, '/store/genres/'),
            json=genre,
            timeout=timeout,
        )
        if create_response.status_code in (200, 201):
            created = create_response.json()
            genres_by_slug[created['slug']] = created['id']
            continue
        if create_response.status_code == 400:
            # Возможен конфликт уникальности из-за
            # параллельного/повторного запуска.
            refresh_response = session.get(
                api_url(base_url, '/store/genres/'),
                timeout=timeout,
            )
            refreshed = ensure_response_ok(
                refresh_response,
                'refresh genres after conflict',
            )
            refreshed_items = extract_results(refreshed)
            genres_by_slug = {
                item['slug']: item['id']
                for item in refreshed_items
                if isinstance(item, dict) and 'slug' in item and 'id' in item
            }
            if genre['slug'] in genres_by_slug:
                continue
        raise RuntimeError(
            f"genre create '{genre['name']}' failed: "
            f'HTTP {create_response.status_code} {create_response.text}',
        )

    return genres_by_slug


def create_album(
    session: requests.Session,
    base_url: str,
    album_payload: dict,
    token: str,
    timeout: int,
) -> int:
    """Todo: docstring."""
    response = session.post(
        api_url(base_url, '/store/albums/'),
        headers={'Authorization': f'Bearer {token}'},
        json=album_payload,
        timeout=timeout,
    )
    data = ensure_response_ok(
        response,
        f"create album '{album_payload['name']}'",
    )
    return data['id']


def create_track(
    session: requests.Session,
    base_url: str,
    track_payload: dict,
    audio_path: Path,
    token: str,
    timeout: int,
) -> None:
    """Todo: docstring."""
    with audio_path.open('rb') as audio_file:
        response = session.post(
            api_url(base_url, '/store/track/'),
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
        )
    ensure_response_ok(response, f"create track '{track_payload['name']}'")


def main() -> int:
    """Todo: docstring."""
    args = parse_args()
    payload_path = Path(args.payload)
    if not payload_path.exists():
        raise FileNotFoundError(f'Payload file not found: {payload_path}')

    data = json.loads(payload_path.read_text(encoding='utf-8'))
    session = requests.Session()
    timeout = args.timeout
    genres_by_slug = ensure_genres(
        session=session,
        base_url=args.base_url,
        genres_payload=data['genres'],
        timeout=timeout,
    )

    with tempfile.NamedTemporaryFile(
        mode='wb',
        suffix='.mp3',
        delete=False,
    ) as audio_tmp:
        audio_tmp.write(b'ID3\x03\x00\x00\x00\x00\x00\x21TEST_FIXTURE_AUDIO')
        audio_path = Path(audio_tmp.name)

    album_count = 0
    track_count = 0
    artist_count = 0
    try:
        for artist in data['artists']:
            token = register_or_login_artist(
                session=session,
                base_url=args.base_url,
                artist=artist,
                password=args.password,
                timeout=timeout,
            )
            update_artist_profile(
                session=session,
                base_url=args.base_url,
                artist=artist,
                token=token,
                timeout=timeout,
            )
            artist_count += 1
            for album in artist['albums']:
                genre_id = genres_by_slug[album['genre_slug']]
                album_id = create_album(
                    session=session,
                    base_url=args.base_url,
                    token=token,
                    timeout=timeout,
                    album_payload={
                        'name': album['name'],
                        'is_single': False,
                        'release_date': album['release_date'],
                        'genre': genre_id,
                        'price': '199.00',
                        'description': (
                            f'{artist["name"]} / {album["name"]} / '
                            f'test import fixture'
                        ),
                        'allow_overpay': False,
                        'visibility': 'public',
                        'is_published': True,
                        'is_active': True,
                    },
                )
                album_count += 1
                for position, track_name in enumerate(
                    album['tracks'],
                    start=1,
                ):
                    create_track(
                        session=session,
                        base_url=args.base_url,
                        token=token,
                        timeout=timeout,
                        audio_path=audio_path,
                        track_payload={
                            'name': track_name,
                            'album': album_id,
                            'position': position,
                            'price': '49.00',
                            'description': (
                                f'{artist["name"]} / '
                                f'{album["name"]} / {track_name}'
                            ),
                        },
                    )
                    track_count += 1
    finally:
        audio_path.unlink(missing_ok=True)

    print(
        'Import completed: '
        f'artists={artist_count}, albums={album_count}, tracks={track_count}, '
        f'genres={len(genres_by_slug)}',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
