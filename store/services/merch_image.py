"""Сервис управления изображениями мерча."""

from django.db import transaction

from store.models import Image, Merch


class MerchImageService:
    """Управляет изображениями мерча и главным изображением."""

    @classmethod
    @transaction.atomic
    def create_image(
        cls,
        *,
        merch: Merch,
        validated_data: dict,
    ) -> Image:
        """Создаёт изображение и назначает главное при необходимости."""
        merch = cls._lock_merch(merch)

        requested_is_main = validated_data.get('is_main', False)
        has_images = Image.objects.filter(merch=merch).exists()

        is_main = requested_is_main or not has_images

        if is_main:
            cls._clear_main_image(merch=merch)

        return Image.objects.create(
            merch=merch,
            image=validated_data['image'],
            is_main=is_main,
        )

    @classmethod
    @transaction.atomic
    def update_image(
        cls,
        *,
        image: Image,
        validated_data: dict,
    ) -> Image:
        """Обновляет изображение и поддерживает главное изображение."""
        merch = cls._lock_merch(image.merch)
        image = Image.objects.select_for_update().get(pk=image.pk)

        requested_is_main = validated_data.get('is_main')
        was_main = image.is_main

        old_image_storage = None
        old_image_name = None

        if 'image' in validated_data:
            old_image_storage = image.image.storage
            old_image_name = image.image.name
            image.image = validated_data['image']

        if requested_is_main is True and not image.is_main:
            cls._clear_main_image(merch=merch)
            image.is_main = True

        elif requested_is_main is False and was_main:
            next_image = cls._get_next_image(
                merch=merch,
                exclude_image_id=image.id,
            )
        if next_image:
            image.is_main = False
            image.save(update_fields=['is_main'])
            next_image.is_main = True
            next_image.save(update_fields=['is_main'])
            return image

            # У единственного фото нельзя снять главный статус:
            # иначе останется набор изображений без главного.

        update_fields = ['is_main']

        if 'image' in validated_data:
            update_fields.append('image')

        image.save(update_fields=update_fields)

        if old_image_name and old_image_name != image.image.name:
            cls._delete_file_after_commit(
                storage=old_image_storage,
                name=old_image_name,
            )

        return image

    @classmethod
    @transaction.atomic
    def delete_image(
        cls,
        *,
        image: Image,
    ) -> None:
        """Удаляет изображение и назначает следующее главным."""
        merch = cls._lock_merch(image.merch)
        image = Image.objects.select_for_update().get(pk=image.pk)

        was_main = image.is_main
        image_storage = image.image.storage
        image_name = image.image.name

        image.delete()

        if was_main:
            next_image = cls._get_next_image(merch=merch)

            if next_image:
                next_image.is_main = True
                next_image.save(update_fields=['is_main'])

        cls._delete_file_after_commit(
            storage=image_storage,
            name=image_name,
        )

    @staticmethod
    def _lock_merch(merch: Merch) -> Merch:
        """Блокирует мерч на время изменения набора изображений."""
        return Merch.objects.select_for_update().get(pk=merch.pk)

    @staticmethod
    def _clear_main_image(*, merch: Merch) -> None:
        """Снимает признак главного изображения у текущего главного фото."""
        Image.objects.filter(
            merch=merch,
            is_main=True,
        ).update(is_main=False)

    @staticmethod
    def _get_next_image(
        *,
        merch: Merch,
        exclude_image_id: int | None = None,
    ) -> Image | None:
        """Возвращает следующее изображение мерча по порядку создания."""
        queryset = Image.objects.filter(merch=merch)

        if exclude_image_id is not None:
            queryset = queryset.exclude(pk=exclude_image_id)

        return queryset.order_by('id').first()

    @staticmethod
    def _delete_file_after_commit(*, storage, name: str) -> None:
        """Удаляет файл из хранилища после успешного коммита транзакции."""
        if not name:
            return

        transaction.on_commit(
            lambda: storage.delete(name),
        )

    @classmethod
    @transaction.atomic
    def ensure_main_image(
        cls,
        *,
        merch: Merch,
    ) -> None:
        """Назначает главное изображение, если у мерча оно отсутствует."""
        merch = cls._lock_merch(merch)

        if Image.objects.filter(
            merch=merch,
            is_main=True,
        ).exists():
            return
        image = (
            Image.objects
            .filter(
                merch=merch,
            )
            .order_by('id')
            .first()
        )

        if image:
            image.is_main = True
            image.save(update_fields=['is_main'])
