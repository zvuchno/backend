"""Тесты механизма удаления контента."""

from unittest.mock import Mock, patch

import pytest
from django.contrib.admin import AdminSite
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status

from store.admin.recording import RecordingAdmin
from store.admin.track import ReleaseTrackAdmin
from store.models import (
    Merch,
    Product,
    ProductVariant,
    Recording,
    ReleaseTrack,
)
from store.services.album_archive import AlbumArchiveScheduler
from store.tests.test_sales_protection import create_order


@pytest.mark.django_db
class TestDeletion:
    """Тесты удаления контента."""

    def test_physical_delete_cascade(self, variant_factory):
        """Физическое удаление → удаляется вся цепочка."""
        variant_merch = variant_factory('merch')
        product = variant_merch.product
        merch = getattr(product, 'merch', None)
        merch_id = merch.id
        prod_id = product.id

        merch.delete()

        assert not Merch.objects.filter(id=merch_id).exists()
        assert not Product.objects.filter(id=prod_id).exists()
        assert not ProductVariant.objects.filter(product_id=prod_id).exists()

    @pytest.mark.parametrize(
        ('factory_attr', 'url_resource_name'),
        [
            ('album', 'albums'),
            ('track', 'tracks'),
            ('merch', 'merch'),
        ],
    )
    def test_soft_delete_deactivates_object_and_variants(
        self,
        artist_client,
        variant_factory,
        factory_attr,
        url_resource_name,
    ):
        """Удаление через API → деактивация контента и его вариантов."""
        variant = variant_factory(factory_attr)
        product = variant.product
        content = getattr(product, factory_attr)

        url = reverse(
            f'api:store:{url_resource_name}-detail',
            args=[content.pk],
        )

        response = artist_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        content.refresh_from_db()
        assert content.is_active is False

        variants = product.variants.all()
        assert variants.exists()
        for v in variants:
            v.refresh_from_db()
            assert v.is_active is False

    @pytest.mark.parametrize('has_sales', [False, True])
    def test_recording_admin_never_allows_physical_delete(
        self,
        admin_client,
        staff_user,
        listener_user,
        variant_factory,
        has_sales,
    ):
        """Recording нельзя удалить из админки при любой истории продаж."""
        variant = variant_factory('track')
        recording = variant.product.track.recording

        if has_sales:
            create_order(listener_user, variant)

        model_admin = RecordingAdmin(Recording, AdminSite())
        request = Mock(user=staff_user)

        assert model_admin.has_delete_permission(request, recording) is False

        response = admin_client.post(
            reverse(
                'admin:store_recording_delete',
                args=(recording.pk,),
            ),
            {'post': 'yes'},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Recording.objects.filter(pk=recording.pk).exists()

    def test_recording_admin_change_page_opens(
        self,
        admin_client,
        variant_factory,
    ):
        """Страница существующей Recording открывается без ошибок."""
        recording = variant_factory('track').product.track.recording

        response = admin_client.get(
            reverse(
                'admin:store_recording_change',
                args=(recording.pk,),
            ),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_release_track_admin_rejects_directly_purchased_track(
        self,
        staff_user,
        listener_user,
        variant_factory,
    ):
        """Отдельно приобретённый ReleaseTrack нельзя удалить."""
        variant = variant_factory('track')
        track = variant.product.track
        create_order(listener_user, variant)
        model_admin = ReleaseTrackAdmin(ReleaseTrack, AdminSite())
        request = Mock(user=staff_user)

        assert model_admin.has_delete_permission(request, track) is False

        with pytest.raises(ValidationError):
            model_admin.delete_model(request, track)

        assert ReleaseTrack.objects.filter(pk=track.pk).exists()

    def test_release_track_admin_rejects_track_from_purchased_release(
        self,
        staff_user,
        listener_user,
        variant_factory,
    ):
        """ReleaseTrack из приобретённого релиза нельзя удалить."""
        album_variant = variant_factory('album')
        track_variant = variant_factory(
            'track',
            album=album_variant.product.album,
        )
        track = track_variant.product.track
        create_order(listener_user, album_variant)
        model_admin = ReleaseTrackAdmin(ReleaseTrack, AdminSite())
        request = Mock(user=staff_user)

        assert model_admin.has_delete_permission(request, track) is False

        with pytest.raises(ValidationError):
            model_admin.delete_model(request, track)

        assert ReleaseTrack.objects.filter(pk=track.pk).exists()

    def test_release_track_admin_deletes_unsold_track_and_updates_release(
        self,
        staff_user,
        variant_factory,
        django_capture_on_commit_callbacks,
    ):
        """Удаление непроданного трека актуализирует релиз и архив."""
        track = variant_factory('track').product.track
        release = track.release
        model_admin = ReleaseTrackAdmin(ReleaseTrack, AdminSite())
        request = Mock(user=staff_user)

        assert model_admin.has_delete_permission(request, track) is True

        with (
            patch(
                'store.admin.track.unpublish_if_empty',
            ) as unpublish_mock,
            patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
            ) as schedule_mock,
            django_capture_on_commit_callbacks(execute=True),
        ):
            model_admin.delete_model(request, track)
            schedule_mock.assert_not_called()

        assert not ReleaseTrack.objects.filter(pk=track.pk).exists()
        unpublish_mock.assert_called_once_with(release)
        schedule_mock.assert_called_once_with(release.pk)

    def test_release_track_admin_rejects_mixed_bulk_delete(
        self,
        staff_user,
        listener_user,
        variant_factory,
    ):
        """Проданный трек блокирует удаление всей смешанной выборки."""
        sold_variant = variant_factory('track')
        sold_track = sold_variant.product.track
        unsold_track = variant_factory('track').product.track
        create_order(listener_user, sold_variant)
        queryset = ReleaseTrack.objects.filter(
            pk__in=(sold_track.pk, unsold_track.pk),
        )
        model_admin = ReleaseTrackAdmin(ReleaseTrack, AdminSite())

        with (
            patch('store.admin.track.unpublish_if_empty') as unpublish_mock,
            patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
            ) as schedule_mock,
            pytest.raises(ValidationError),
        ):
            model_admin.delete_queryset(
                Mock(user=staff_user),
                queryset,
            )

        assert (
            ReleaseTrack.objects.filter(
                pk__in=(sold_track.pk, unsold_track.pk),
            ).count()
            == 2
        )
        unpublish_mock.assert_not_called()
        schedule_mock.assert_not_called()

    def test_release_track_admin_bulk_delete_updates_all_releases(
        self,
        staff_user,
        variant_factory,
        django_capture_on_commit_callbacks,
    ):
        """Массовое удаление обновляет каждый затронутый релиз и архив."""
        tracks = [
            variant_factory('track').product.track,
            variant_factory('track').product.track,
        ]
        track_ids = {track.pk for track in tracks}
        release_ids = {track.release_id for track in tracks}
        queryset = ReleaseTrack.objects.filter(pk__in=track_ids)
        model_admin = ReleaseTrackAdmin(ReleaseTrack, AdminSite())

        with (
            patch(
                'store.admin.track.unpublish_if_empty',
            ) as unpublish_mock,
            patch.object(
                AlbumArchiveScheduler,
                'schedule_by_id',
            ) as schedule_mock,
            django_capture_on_commit_callbacks(execute=True),
        ):
            model_admin.delete_queryset(
                Mock(user=staff_user),
                queryset,
            )
            schedule_mock.assert_not_called()

        assert not ReleaseTrack.objects.filter(pk__in=track_ids).exists()
        assert {
            call.args[0].pk for call in unpublish_mock.call_args_list
        } == release_ids
        assert {
            call.args[0] for call in schedule_mock.call_args_list
        } == release_ids
        assert len(release_ids) == 2
