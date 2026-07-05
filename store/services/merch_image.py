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
        """Создаёт изображение и при необходимости назначает его главным."""
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
        image_changed = 'image' in validated_data

        old_image_storage = None
        old_image_name = None

        if image_changed:
            old_image_storage = image.image.storage
            old_image_name = image.image.name
            image.image = validated_data['image']

        if requested_is_main is True and not was_main:
            cls._clear_main_image(merch=merch)
            image.is_main = True

        elif requested_is_main is False and was_main:
            next_image = cls._get_next_image(
                merch=merch,
                exclude_image_id=image.id,
            )

            if next_image:
                # Сначала снимаем главный статус с текущего изображения:
                # иначе unique constraint не позволит назначить следующее.
                image.is_main = False

                update_fields = ['is_main']
                if image_changed:
                    update_fields.append('image')

                image.save(update_fields=update_fields)

                next_image.is_main = True
                next_image.save(update_fields=['is_main'])

                cls._delete_replaced_file_after_commit(
                    storage=old_image_storage,
                    old_name=old_image_name,
                    new_name=image.image.name,
                )

                return image

            # У единственного изображения нельзя снять главный статус:
            # иначе у мерча останется фото без главного.

        update_fields = []

        if image_changed:
            update_fields.append('image')

        if image.is_main != was_main:
            update_fields.append('is_main')

        if update_fields:
            image.save(update_fields=update_fields)

        cls._delete_replaced_file_after_commit(
            storage=old_image_storage,
            old_name=old_image_name,
            new_name=image.image.name,
        )

        return image

    @classmethod
    @transaction.atomic
    def delete_image(
        cls,
        *,
        image: Image,
    ) -> None:
        """Удаляет изображение и, если надо, назначает следующее главным."""
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

    @staticmethod
    def _lock_merch(merch: Merch) -> Merch:
        """Блокирует мерч на время изменения набора изображений."""
        return Merch.objects.select_for_update().get(pk=merch.pk)

    @staticmethod
    def _clear_main_image(*, merch: Merch) -> None:
        """Снимает главный статус с текущего главного изображения."""
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
    def _delete_replaced_file_after_commit(
        cls,
        *,
        storage,
        old_name: str | None,
        new_name: str,
    ) -> None:
        """Удаляет заменённый файл после успешного коммита транзакции."""
        if not old_name or old_name == new_name:
            return

        cls._delete_file_after_commit(
            storage=storage,
            name=old_name,
        )
