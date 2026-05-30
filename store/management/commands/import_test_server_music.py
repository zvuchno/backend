"""Импорт тестового музыкального набора через внутренний API.

Команда не пишет данные напрямую в модели: создание происходит
через API-эндпоинты проекта, чтобы сохранить бизнес-валидации
и сайд-эффекты сериализаторов.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.test.utils import override_settings
from rest_framework.test import APIClient
from rest_framework.views import APIView

from scripts.test_content.constants import AUDIO_FIXTURE, FIXTURE_NAMESPACE
from scripts.test_content.images import generated_png_bytes
from scripts.test_content.matching import match_merch_kinds

from store.models import Genre, MerchKind


@contextmanager
def disabled_api_throttling():
    """Временно отключает DRF throttling на время импорта через APIClient."""
    original_get_throttles = APIView.get_throttles

    try:
        APIView.get_throttles = lambda self: []
        yield
    finally:
        APIView.get_throttles = original_get_throttles


class Command(BaseCommand):
    """Импортирует тестовые музыкальные данные через API."""

    help = (
        'Импортирует тестовые данные через API '
        '(жанры, типы мерча, артисты, альбомы, треки, мерч).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--payload',
            default=str(
                Path(__file__).resolve().parents[3]
                / 'scripts'
                / 'data'
                / 'test_server_friendly_indie_payload.json',
            ),
            help='Путь к JSON-датасету.',
        )
        parser.add_argument(
            '--password',
            default='TestPass123!@#',
            help='Пароль для fixture-аккаунтов артистов.',
        )
        parser.add_argument(
            '--disable-throttling',
            action='store_true',
            help=(
                'Отключить DRF throttling на время импорта. '
                'Без флага команда ждет и повторяет запросы при HTTP 429.'
            ),
        )

    def handle(self, *args, **options):  # noqa: C901
        payload_path = Path(options['payload'])
        password = options['password']
        disable_throttling = options['disable_throttling']
        if not payload_path.exists():
            raise CommandError(f'Payload file not found: {payload_path}')

        data = json.loads(payload_path.read_text(encoding='utf-8'))

        with (
            override_settings(
                ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'],
            ),
            disabled_api_throttling() if disable_throttling else nullcontext(),
        ):
            client = APIClient()
            genres_by_slug = self._ensure_genres(
                data.get('genres', []),
            )

            artists_created = 0
            albums_created = 0
            tracks_created = 0
            merch_created = 0
            merch_images_created = 0
            merch_skipped = 0
            merch_kinds_by_slug = self._ensure_merch_kinds(
                data.get('merch_kinds', []),
            )
            merch_templates = data.get('merch_templates', [])

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
                album_id_by_marker = self._ids_by_marker(
                    existing_albums,
                    'album',
                )
                album_ids_by_index = {}

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
                    album_ids_by_index[album_index] = album_id

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

                existing_merch = self._list_merch(client, token)
                merch_id_by_marker = self._ids_by_marker(
                    existing_merch,
                    'merch',
                )
                merch_payloads = [
                    self._format_merch(item, artist)
                    for item in [*merch_templates, *artist.get('merch', [])]
                ]
                for merch_index, merch in enumerate(merch_payloads, start=1):
                    kind_slug = merch['kind_slug']
                    kind_id = merch_kinds_by_slug.get(kind_slug)
                    if kind_id is None:
                        merch_skipped += 1
                        continue
                    merch_marker = self._merch_marker(
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
                        merch_id = self._create_merch(
                            client=client,
                            token=token,
                            merch=merch,
                            merch_marker=merch_marker,
                            kind_id=kind_id,
                            album_id=album_id,
                        )
                        merch_created += 1
                        merch_id_by_marker[merch_marker] = merch_id
                    image_created = self._ensure_merch_image(
                        client,
                        token,
                        merch_id,
                        {
                            **merch,
                            'artist_slug': artist['slug'],
                            'album_seed': album_id,
                        },
                    )
                    if image_created:
                        merch_images_created += 1

            self.stdout.write(
                self.style.SUCCESS(
                    'Import completed: '
                    f'artists_created={artists_created}, '
                    f'albums_created={albums_created}, '
                    f'tracks_created={tracks_created}, '
                    f'merch_created={merch_created}, '
                    f'merch_images_created={merch_images_created}, '
                    f'merch_skipped={merch_skipped}, '
                    f'genres_total={len(genres_by_slug)}, '
                    f'merch_kinds_matched={len(merch_kinds_by_slug)}',
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
        return (
            f'[fixture:{FIXTURE_NAMESPACE}:album:{artist_slug}:{album_index}]'
        )

    @staticmethod
    def _merch_marker(
        artist_slug: str,
        kind_slug: str,
        merch_index: int,
    ) -> str:
        return (
            f'[fixture:{FIXTURE_NAMESPACE}:merch:{artist_slug}:'
            f'{kind_slug}:{merch_index}]'
        )

    @staticmethod
    def _image_upload(
        seed: str,
        subject: str,
        filename: str,
    ) -> SimpleUploadedFile:
        return SimpleUploadedFile(
            name=filename,
            content=generated_png_bytes(seed, subject),
            content_type='image/png',
        )

    @staticmethod
    def _throttle_wait_seconds(response) -> int:
        """Возвращает время ожидания для повторного запроса после 429."""
        retry_after = response.headers.get('Retry-After')
        if retry_after and retry_after.isdigit():
            return max(1, int(retry_after))

        match = re.search(
            r'Expected available in (\d+) seconds?',
            response.content.decode(errors='ignore'),
        )
        if match:
            return max(1, int(match.group(1)))

        return 1

    @classmethod
    def _api_json(
        cls,
        client: APIClient,
        method: str,
        path: str,
        token: str | None = None,
        max_attempts: int = 5,
        **kwargs,
    ) -> APIClient.response_class:
        """Выполняет API-запрос и повторяет его при DRF throttling."""
        headers = {}
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'

        response = None
        for attempt in range(max_attempts):
            response = getattr(client, method)(path, **headers, **kwargs)
            if response.status_code != 429:
                return response

            if attempt == max_attempts - 1:
                return response

            time.sleep(cls._throttle_wait_seconds(response))

        return response

    def _ensure_genres(
        self,
        genres_payload: list[dict],
    ) -> dict[str, int]:
        genres_by_slug: dict[str, int] = {}
        for genre in genres_payload:
            existing = (
                Genre.objects.filter(slug=genre['slug']).first()
                or Genre.objects.filter(name__iexact=genre['name']).first()
            )
            if existing is None:
                existing = Genre.objects.create(
                    name=genre['name'],
                    slug=genre['slug'],
                )
            genres_by_slug[genre['slug']] = existing.id
        return genres_by_slug

    @staticmethod
    def _merch_kind_items() -> list[dict]:
        return [
            {'id': item.id, 'name': item.name, 'slug': item.slug}
            for item in MerchKind.objects.all()
        ]

    def _ensure_merch_kinds(
        self,
        merch_kinds_payload: list[dict],
    ) -> dict[str, int]:
        matched = match_merch_kinds(self._merch_kind_items())
        for merch_kind in merch_kinds_payload:
            canonical_slug = merch_kind['slug']
            if canonical_slug in matched:
                continue
            MerchKind.objects.get_or_create(
                slug=canonical_slug,
                defaults={'name': merch_kind['name']},
            )
            matched = match_merch_kinds(self._merch_kind_items())
        return matched

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
        current_response = self._api_json(
            client,
            'get',
            '/api/v1/artists/me/',
            token=token,
        )
        if current_response.status_code != 200:
            raise CommandError(
                f"Artist profile read failed for '{artist['name']}': "
                f'HTTP {current_response.status_code} '
                f'{current_response.content.decode()}',
            )
        if current_response.json().get('cover'):
            return
        cover_response = self._api_json(
            client,
            'patch',
            '/api/v1/artists/me/cover/',
            token=token,
            data={
                'cover': self._image_upload(
                    artist['slug'],
                    'artist',
                    f'{artist["slug"]}-artist.png',
                ),
            },
        )
        if cover_response.status_code != 200:
            raise CommandError(
                f"Artist cover upload failed for '{artist['name']}': "
                f'HTTP {cover_response.status_code} '
                f'{cover_response.content.decode()}',
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
                'price': album.get('price', '199.00'),
                'description': (
                    f'{album_marker} {artist["name"]} / {album["name"]} / '
                    'test import fixture'
                ),
                'cover_image': self._image_upload(
                    f'{artist["slug"]}:{album["name"]}',
                    'album',
                    f'{artist["slug"]}-album.png',
                ),
                'allow_overpay': album.get('allow_overpay', False),
                'visibility': album.get('visibility', 'public'),
                'is_published': album.get('is_published', True),
                'is_active': True,
            },
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
            content=AUDIO_FIXTURE,
            content_type='audio/mpeg',
        )
        response = self._api_json(
            client,
            'post',
            '/api/v1/store/tracks/',
            token=token,
            data={
                'name': track_name,
                'album': str(album_id),
                'position': str(position),
                'price': album.get('track_price', '49.00'),
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
        return self._paginated_get(
            client,
            '/api/v1/store/tracks/',
            token=token,
        )

    @staticmethod
    def _format_merch(raw: dict, artist: dict) -> dict:
        result = dict(raw)
        for key in ('name', 'description', 'property_name'):
            if isinstance(result.get(key), str):
                result[key] = result[key].format(
                    artist=artist['name'],
                    artist_slug=artist['slug'],
                )
        return result

    def _create_merch(
        self,
        client: APIClient,
        token: str,
        merch: dict,
        merch_marker: str,
        kind_id: int,
        album_id: int | None,
    ) -> int:
        data = {
            'name': merch['name'],
            'kind': kind_id,
            'price': merch.get('price', '999.00'),
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

        response = self._api_json(
            client,
            'post',
            '/api/v1/store/merch/',
            token=token,
            data=data,
            format='json',
        )
        if response.status_code not in (200, 201):
            raise CommandError(
                f"Merch create failed for '{merch['name']}': "
                f'HTTP {response.status_code} {response.content.decode()}',
            )
        return response.json()['id']

    def _ensure_merch_image(
        self,
        client: APIClient,
        token: str,
        merch_id: int,
        merch: dict,
    ) -> bool:
        detail_response = self._api_json(
            client,
            'get',
            f'/api/v1/store/merch/{merch_id}/',
            token=token,
        )
        if detail_response.status_code != 200:
            raise CommandError(
                f'Merch read failed for id={merch_id}: '
                f'HTTP {detail_response.status_code} '
                f'{detail_response.content.decode()}',
            )
        detail = detail_response.json()
        if detail.get('main_image') or detail.get('images_merch'):
            return False

        response = self._api_json(
            client,
            'post',
            f'/api/v1/store/merch/{merch_id}/images/',
            token=token,
            data={
                'is_main': True,
                'image': self._image_upload(
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
        )
        if response.status_code not in (200, 201):
            raise CommandError(
                f"Merch image upload failed for '{merch.get('name')}': "
                f'HTTP {response.status_code} {response.content.decode()}',
            )
        return True

    def _list_merch(self, client: APIClient, token: str) -> list[dict]:
        return self._paginated_get(client, '/api/v1/store/merch/', token=token)

    @staticmethod
    def _ids_by_marker(items: list[dict], kind: str) -> dict[str, int]:
        prefix = f'[fixture:{FIXTURE_NAMESPACE}:{kind}:'
        result = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            description = str(item.get('description', ''))
            item_id = item.get('id')
            if not item_id:
                continue
            start = description.find(prefix)
            end = description.find(']', start + 1)
            if start >= 0 and end > start:
                marker = description[start : end + 1]
                result[marker] = item_id
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
