"""Импорт тестового музыкального набора через внутренний API.

Команда не пишет данные напрямую в модели: создание происходит
через API-эндпоинты проекта, чтобы сохранить бизнес-валидации
и сайд-эффекты сериализаторов.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.test.utils import override_settings
from rest_framework.test import APIClient


class Command(BaseCommand):
    """Импортирует тестовые музыкальные данные через API."""

    help = (
        'Импортирует тестовые музыкальные данные через API '
        '(жанры, артисты, альбомы, треки).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--payload',
            default=str(
                Path(__file__).resolve().parents[3]
                / 'scripts'
                / 'data'
                / 'test_server_music_payload.json',
            ),
            help='Путь к JSON-датасету.',
        )
        parser.add_argument(
            '--password',
            default='TestPass123!@#',
            help='Пароль для fixture-аккаунтов артистов.',
        )

    def handle(self, *args, **options):
        payload_path = Path(options['payload'])
        password = options['password']
        if not payload_path.exists():
            raise CommandError(f'Payload file not found: {payload_path}')

        data = json.loads(payload_path.read_text(encoding='utf-8'))

        with override_settings(
            ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
        ):
            client = APIClient()
            genres_by_slug = self._ensure_genres(
                client,
                data.get('genres', []),
            )

            artists_created = 0
            albums_created = 0
            tracks_created = 0

            for artist in data.get('artists', []):
                token, artist_was_created = self._register_or_login_artist(
                    client=client,
                    artist=artist,
                    password=password,
                )
                if artist_was_created:
                    artists_created += 1
                self._update_artist_profile(client, artist, token)

                existing_albums = self._list_albums(client, token)
                album_id_by_marker = self._albums_by_marker(existing_albums)

                for album_index, album in enumerate(
                    artist.get('albums', []),
                    start=1,
                ):
                    album_marker = self._album_marker(
                        artist['slug'],
                        album_index,
                    )
                    album_id = album_id_by_marker.get(album_marker)
                    if album_id is None:
                        genre_id = genres_by_slug[album['genre_slug']]
                        album_id = self._create_album(
                            client=client,
                            token=token,
                            artist=artist,
                            album=album,
                            genre_id=genre_id,
                            album_marker=album_marker,
                        )
                        albums_created += 1
                        album_id_by_marker[album_marker] = album_id

                    existing_tracks = self._list_tracks(client, token)
                    track_keys = {
                        (
                            track.get('album'),
                            track.get('position'),
                            track.get('name'),
                        )
                        for track in existing_tracks
                        if isinstance(track, dict)
                    }
                    for position, track_name in enumerate(
                        album.get('tracks', []),
                        start=1,
                    ):
                        track_key = (album_id, position, track_name)
                        if track_key in track_keys:
                            continue
                        self._create_track(
                            client=client,
                            token=token,
                            artist=artist,
                            album=album,
                            album_id=album_id,
                            track_name=track_name,
                            position=position,
                        )
                        tracks_created += 1
                        track_keys.add(track_key)

            self.stdout.write(
                self.style.SUCCESS(
                    'Import completed: '
                    f'artists_created={artists_created}, '
                    f'albums_created={albums_created}, '
                    f'tracks_created={tracks_created}, '
                    f'genres_total={len(genres_by_slug)}',
                ),
            )

    @staticmethod
    def _normalize_username(source: str) -> str:
        return ''.join(
            char if char.isalnum() else '-' for char in source.lower()
        ).strip('-')

    @staticmethod
    def _stable_phone(seed: str) -> str:
        digest = hashlib.sha256(seed.encode('utf-8')).hexdigest()
        suffix = f'{int(digest[:12], 16) % 10_000_000_000:010d}'
        return f'+7{suffix}'

    @staticmethod
    def _album_marker(artist_slug: str, album_index: int) -> str:
        return f'[fixture:test_server_music:{artist_slug}:{album_index}]'

    @staticmethod
    def _api_json(
        client: APIClient,
        method: str,
        path: str,
        token: str | None = None,
        **kwargs,
    ) -> APIClient.response_class:
        headers = {}
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return getattr(client, method)(path, **headers, **kwargs)

    def _ensure_genres(
        self,
        client: APIClient,
        genres_payload: list[dict],
    ) -> dict[str, int]:
        genres = self._paginated_get(client, '/api/v1/store/genres/')
        genres_by_slug = {
            genre['slug']: genre['id']
            for genre in genres
            if isinstance(genre, dict) and 'slug' in genre and 'id' in genre
        }
        for genre in genres_payload:
            if genre['slug'] in genres_by_slug:
                continue
            response = self._api_json(
                client,
                'post',
                '/api/v1/store/genres/',
                data=genre,
                format='json',
            )
            if response.status_code in (200, 201):
                payload = response.json()
                genres_by_slug[payload['slug']] = payload['id']
                continue
            if response.status_code == 400:
                # Повторный запуск: объект мог быть создан ранее.
                refreshed = self._paginated_get(
                    client,
                    '/api/v1/store/genres/',
                )
                refreshed_map = {
                    item['slug']: item['id']
                    for item in refreshed
                    if isinstance(item, dict)
                    and 'slug' in item
                    and 'id' in item
                }
                existing_id = refreshed_map.get(genre['slug'])
                if existing_id is not None:
                    genres_by_slug = refreshed_map
                    continue
            raise CommandError(
                f"Genre create failed for '{genre.get('name')}': "
                f'HTTP {response.status_code} {response.content.decode()}',
            )
        return genres_by_slug

    def _register_or_login_artist(
        self,
        client: APIClient,
        artist: dict,
        password: str,
    ) -> tuple[str, bool]:
        username_seed = self._normalize_username(artist['slug'])
        username = f'fixture-{username_seed}'
        email = f'{username_seed}@fixtures.zvuchno.local'
        phone = self._stable_phone(username_seed)

        register_response = self._api_json(
            client,
            'post',
            '/api/v1/auth/register/artist/',
            data={
                'username': username,
                'email': email,
                'phone': phone,
                'name': artist['name'],
                'password': password,
            },
            format='json',
        )
        if register_response.status_code not in (200, 201, 400):
            raise CommandError(
                f"Artist register failed for '{artist['name']}': "
                f'HTTP {register_response.status_code} '
                f'{register_response.content.decode()}',
            )
        created = register_response.status_code in (200, 201)

        token_response = self._api_json(
            client,
            'post',
            '/api/v1/auth/token/create/',
            data={'email': email, 'password': password},
            format='json',
        )
        if token_response.status_code != 200:
            raise CommandError(
                f"Token create failed for '{artist['name']}' ({email}). "
                'Проверь пароль --password и существующие аккаунты. '
                f'HTTP {token_response.status_code} '
                f'{token_response.content.decode()}',
            )
        access = token_response.json().get('access')
        if not access:
            raise CommandError(f"Access token missing for '{artist['name']}'")
        return access, created

    def _update_artist_profile(
        self,
        client: APIClient,
        artist: dict,
        token: str,
    ) -> None:
        response = self._api_json(
            client,
            'patch',
            '/api/v1/artists/me/',
            token=token,
            data={
                'name': artist['name'],
                'city': artist.get('city', ''),
                'description': (
                    f'{artist["name"]} ({artist.get("genre_slug", "music")}) '
                    'imported as test fixture via API command'
                ),
                'url': f'https://fixtures.zvuchno.local/artists/{artist["slug"]}',
            },
            format='json',
        )
        if response.status_code != 200:
            raise CommandError(
                f"Artist profile update failed for '{artist['name']}': "
                f'HTTP {response.status_code} {response.content.decode()}',
            )

    def _create_album(
        self,
        client: APIClient,
        token: str,
        artist: dict,
        album: dict,
        genre_id: int,
        album_marker: str,
    ) -> int:
        response = self._api_json(
            client,
            'post',
            '/api/v1/store/albums/',
            token=token,
            data={
                'name': album['name'],
                'is_single': False,
                'release_date': album['release_date'],
                'genre': genre_id,
                'price': '199.00',
                'description': (
                    f'{album_marker} {artist["name"]} / {album["name"]} / '
                    'test import fixture'
                ),
                'allow_overpay': False,
                'visibility': 'public',
                'is_published': True,
                'is_active': True,
            },
            format='json',
        )
        if response.status_code not in (200, 201):
            raise CommandError(
                f"Album create failed for '{album['name']}': "
                f'HTTP {response.status_code} {response.content.decode()}',
            )
        return response.json()['id']

    def _create_track(
        self,
        client: APIClient,
        token: str,
        artist: dict,
        album: dict,
        album_id: int,
        track_name: str,
        position: int,
    ) -> None:
        dummy_audio = SimpleUploadedFile(
            name='fixture.mp3',
            content=b'ID3\x03\x00\x00\x00\x00\x00\x21TEST_FIXTURE_AUDIO',
            content_type='audio/mpeg',
        )
        response = self._api_json(
            client,
            'post',
            '/api/v1/store/track/',
            token=token,
            data={
                'name': track_name,
                'album': str(album_id),
                'position': str(position),
                'price': '49.00',
                'allow_overpay': 'false',
                'description': f'{artist["name"]} / '
                f'{album["name"]} / {track_name}',
                'audio_file': dummy_audio,
            },
        )
        if response.status_code not in (200, 201):
            raise CommandError(
                f"Track create failed for '{track_name}': "
                f'HTTP {response.status_code} {response.content.decode()}',
            )

    def _list_albums(self, client: APIClient, token: str) -> list[dict]:
        return self._paginated_get(
            client,
            '/api/v1/store/albums/',
            token=token,
        )

    def _list_tracks(self, client: APIClient, token: str) -> list[dict]:
        return self._paginated_get(client, '/api/v1/store/track/', token=token)

    @staticmethod
    def _albums_by_marker(albums: list[dict]) -> dict[str, int]:
        result = {}
        for album in albums:
            if not isinstance(album, dict):
                continue
            description = str(album.get('description', ''))
            album_id = album.get('id')
            if not album_id:
                continue
            start = description.find('[fixture:test_server_music:')
            end = description.find(']', start + 1)
            if start >= 0 and end > start:
                marker = description[start : end + 1]
                result[marker] = album_id
        return result

    def _paginated_get(
        self,
        client: APIClient,
        path: str,
        token: str | None = None,
    ) -> list[dict]:
        items: list[dict] = []
        limit = 200
        offset = 0
        while True:
            separator = '&' if '?' in path else '?'
            response = self._api_json(
                client,
                'get',
                f'{path}{separator}limit={limit}&offset={offset}',
                token=token,
            )
            if response.status_code != 200:
                raise CommandError(
                    f'GET failed for {path}: '
                    f'HTTP {response.status_code} {response.content.decode()}',
                )
            payload = response.json()
            if isinstance(payload, list):
                items.extend(payload)
                break
            batch = payload.get('results', [])
            if not isinstance(batch, list):
                raise CommandError(f'Unexpected payload for {path}: {payload}')
            items.extend(batch)
            if not payload.get('next'):
                break
            offset += limit
        return items
