from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from rest_framework.exceptions import PermissionDenied, ValidationError

from common.access import can_manage_artist

from store.constants import SINGLE_TRACK_COUNT_ERROR, ZERO_MONEY
from store.models import Album, Recording, ReleaseTrack
from store.policies.recording import can_use_recording_in_release
from store.services import ProductService
from store.services.album_archive import AlbumArchiveScheduler
from store.validators import validate_isrc_format


class TrackService:
    """Операции над треками релиза."""

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        release: Album,
        created_by,
        name: str,
        description: str = '',
        audio_file=None,
        isrc: str | None = None,
        pending_upload: bool = False,
    ) -> ReleaseTrack:
        """Создаёт новую запись и её первое размещение в релизе."""
        isrc = isrc or None

        if isrc is not None:
            validate_isrc_format(isrc)

        release = Album.objects.select_for_update().get(pk=release.pk)

        recording_data = {
            'owner': release.artist,
            'created_by': created_by,
            'name': name,
            'description': description,
            'isrc': isrc,
        }

        if audio_file is not None:
            recording_data['audio_file'] = audio_file

        recording = Recording.objects.create(**recording_data)

        if pending_upload:
            position = None
        else:
            last_position = (
                ReleaseTrack.objects.filter(
                    release=release,
                    position__isnull=False,
                ).aggregate(
                    max_position=Max('position'),
                )
            )['max_position']

            position = (last_position or 0) + 1

        return ReleaseTrack.objects.create(
            release=release,
            recording=recording,
            position=position,
            is_active=not pending_upload,
        )

    @classmethod
    @transaction.atomic
    def add_recording(
        cls,
        *,
        release: Album,
        recording: Recording,
        user,
        price: Decimal | None = None,
        allow_overpay: bool = False,
    ) -> ReleaseTrack:
        """Добавляет существующую запись в релиз."""
        release = (
            Album.objects
            .select_for_update(of=('self',))
            .select_related('artist__label')
            .get(pk=release.pk)
        )

        recording = Recording.objects.select_related('owner__label').get(
            pk=recording.pk,
        )

        if not can_manage_artist(user, release.artist):
            raise PermissionDenied(
                'Нет прав на управление релизом.',
            )

        if not can_manage_artist(user, recording.owner):
            raise PermissionDenied(
                'Нет прав на использование записи.',
            )

        if not can_use_recording_in_release(recording, release):
            raise ValidationError({
                'recording_id': (
                    'Запись нельзя разместить в релизе этого артиста.'
                ),
            })

        if not recording.is_active or not recording.audio_file:
            raise ValidationError({
                'recording_id': 'Запись недоступна для размещения.',
            })

        if price is not None and price < ZERO_MONEY:
            raise ValidationError({
                'price': 'Цена не может быть отрицательной.',
            })

        if ReleaseTrack.objects.filter(
            release=release,
            recording=recording,
        ).exists():
            raise ValidationError({
                'recording_id': 'Запись уже добавлена в этот релиз.',
            })

        if release.release_type == Album.ReleaseType.SINGLE:
            if price is not None or allow_overpay:
                raise ValidationError({
                    'price': (
                        'Для сингла нельзя задавать индивидуальную '
                        'цену и переплату за трек.'
                    ),
                })

            if (
                release.is_published
                and release.tracks.filter(is_active=True).exists()
            ):
                raise ValidationError({
                    'release': SINGLE_TRACK_COUNT_ERROR,
                })

        last_position = (
            ReleaseTrack.objects.filter(
                release=release,
                position__isnull=False,
            ).aggregate(max_position=Max('position'))
        )['max_position']

        track = ReleaseTrack.objects.create(
            release=release,
            recording=recording,
            position=(last_position or 0) + 1,
            is_active=True,
        )

        ProductService.ensure_commerce(
            track,
            validated_data={
                'price': price if price is not None else ZERO_MONEY,
                'allow_overpay': allow_overpay,
            },
        )

        transaction.on_commit(
            lambda release_id=release.pk: AlbumArchiveScheduler.schedule_by_id(
                release_id,
            ),
        )

        return track
