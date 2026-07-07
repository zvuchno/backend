"""Модуль админки для модели Album.

Содержит настройку интерфейса Django Admin для модели альбомов.
"""

import json
from decimal import ROUND_HALF_UP, Decimal
from http import HTTPStatus

from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator
from django.db import transaction
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.urls import path, reverse
from django.utils.html import format_html
from nested_admin.nested import (
    NestedModelAdmin,
    NestedStackedInline,
    NestedTabularInline,
)

from .forms import MoneyForm
from .mixins import (
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
)
from store.constants import (
    MAX_PRICE_DIGITS,
    MONEY_DISPLAY_PRECISION,
)
from store.models import (
    Album,
    AlbumArchive,
    Product,
    Track,
    TrackGeneratedAudio,
    TrackUpload,
)
from store.services import ProductService
from store.services.track_upload import (
    TrackUploadService,
    TrackUploadStorageError,
    TrackUploadStorageService,
    TrackUploadTransportService,
    UploadTransportConfigurationError,
)


class TrackInlineForm(MoneyForm):
    """Форма для TrackInline с редактированием цены из связанного Product.

    Особенности:
    - Добавляет виртуальное поле 'price', которого нет в модели Track.
    Оно отображает и редактирует 'Product.price'.
    - Цепочка save_m2m сохраняет существующую логику других inline-форм.
    - Использует атомарную транзакцию при сохранении цены.
    """

    price = forms.DecimalField(
        label='Цена',
        max_digits=MAX_PRICE_DIGITS,
        decimal_places=MONEY_DISPLAY_PRECISION,
        validators=[MinValueValidator(Decimal('0.00'))],
        initial=Decimal('0.00'),
        required=False,
    )

    class Meta:
        model = Track
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        """Инициализация формы с подстановкой цены из связанного Product."""
        super().__init__(*args, **kwargs)

        product = getattr(self.instance, 'product', None)

        if product:
            # Если Product существует, подставляем его цену в initial
            self.fields['price'].initial = product.price.quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP,
            )

    def save(self, commit=True):
        """Сохраняет Track и синхронизирует цену с Product.

        Особенности:
        - создаёт Product, если его нет.
        - обновляет цену, только если пользователь ввёл новое значение.
        - Если commit=True, вызываем sync_price сразу.
        - Если commit=False, цепляем sync_price к save_m2m,
        сохраняя существующую логику.
        """
        # Сохраняем Track (может быть commit=False)
        instance = super().save(commit=commit)
        # Берём цену из формы, 0.00 если поле пустое
        price = self.cleaned_data.get('price') or Decimal('0.00')

        def sync_commerce() -> None:
            """Синхронизирует коммерческие данные через ProductService."""
            validated_data = {
                'price': price,
                'variants': [],
            }
            ProductService.ensure_commerce(
                instance,
                validated_data=validated_data,
            )

        if commit:
            # Для обычного сохранения вызываем сразу
            sync_commerce()
        else:
            # Для inline-форм в админке: цепляем к save_m2m
            original_save_m2m = getattr(self, 'save_m2m', None)

            def chained_save_m2m() -> None:
                # Сначала вызываем существующий save_m2m, если есть
                if original_save_m2m:
                    original_save_m2m()
                # Затем синхронизируем цену
                sync_commerce()

            self.save_m2m = chained_save_m2m
        return instance


class TrackInline(NestedTabularInline):
    """Инлайн для списка треков (модель Track)."""

    model = Track
    form = TrackInlineForm
    fields = (
        'position',
        'name',
        'duration',
        'preview_player',
        'audio_status',
        'is_active',
        'price',
    )
    readonly_fields = (
        'duration',
        'preview_player',
        'audio_status',
    )
    extra = 0  # Чтобы Nested-сортировка не требовала заполнять пустое поле
    max_num = 0
    show_change_link = True
    ordering = ('position',)
    sortable_field_name = 'position'

    def get_queryset(self, request):
        """Возвращает только финализированные треки альбома."""
        qs = super().get_queryset(request)

        return (
            qs
            .filter(
                audio_file__isnull=False,
            )
            .exclude(
                audio_file='',
            )
            .select_related(
                'product',
                'generated',
            )
        )

    def has_add_permission(self, request, obj=None):
        """Запрещает создание треков через inline."""
        return False

    @admin.display(description='Превью')
    def preview_player(self, obj):
        """Показывает проигрыватель готового превью трека."""
        try:
            generated = obj.generated
        except TrackGeneratedAudio.DoesNotExist:
            return 'Ожидает обработки'

        if (
            generated.preview_status
            == TrackGeneratedAudio.ProcessingStatus.FAILED
        ):
            return format_html(
                '<span class="errornote">Ошибка подготовки</span>',
            )

        if (
            generated.preview_status
            != TrackGeneratedAudio.ProcessingStatus.READY
        ):
            return generated.get_preview_status_display()

        if not generated.preview_file:
            return 'Файл не создан'

        return format_html(
            '<audio controls preload="none" src="{}"></audio>',
            generated.preview_file.url,
        )

    @admin.display(description='Аудио')
    def audio_status(self, obj):
        """Показывает компактные статусы производных аудиофайлов."""
        try:
            generated = obj.generated
        except TrackGeneratedAudio.DoesNotExist:
            return 'Ожидает обработки'

        preview = self._processing_status(
            status=generated.preview_status,
            error=generated.preview_error,
        )
        stream = self._processing_status(
            status=generated.stream_status,
            error=generated.stream_error,
        )

        return format_html(
            'Preview: {}<br>Stream: {}',
            preview,
            stream,
        )

    @staticmethod
    def _processing_status(*, status, error) -> str:
        """Возвращает краткий HTML-статус подготовки файла."""
        if status == TrackGeneratedAudio.ProcessingStatus.READY:
            return format_html('<span class="yes"> готов</span>')

        if status == TrackGeneratedAudio.ProcessingStatus.FAILED:
            return format_html(
                '<span class="errornote">✕ {}</span>',
                error or 'ошибка',
            )

        if status == TrackGeneratedAudio.ProcessingStatus.BUILDING:
            return ' подготавливается'

        return ' ожидает'


class ProductInline(NestedStackedInline):
    """Инлайн продукта с вложенными вариантами."""

    model = Product
    form = MoneyForm
    fields = ('price', 'allow_overpay')
    can_delete = False
    verbose_name = 'Торговые настройки альбома'


class AlbumArchiveInline(NestedStackedInline):
    """Инлайн подготовленного архива альбома."""

    model = AlbumArchive
    can_delete = False
    extra = 0
    max_num = 0
    fields = (
        'file',
        'status',
        'content_hash',
        'pending_hash',
        'error_message',
        'created_at',
        'updated_at',
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        """Запрещает ручное создание архива через админку."""
        return False

    def has_change_permission(self, request, obj=None):
        """Запрещает ручное редактирование архива через админку."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Запрещает ручное удаление архива через админку."""
        return False


@admin.register(Album)
class AlbumAdmin(
    AutoOwnerAdminMixin,
    CommerceBaseMixin,
    CommerceDisplayMixin,
    NestedModelAdmin,
):
    """Админка модели Album с поддержкой вложенных inline.

    Отображает:
    - Основные поля альбома.
    - Инлайн Product и его варианты (ProductInline).
    - Инлайн Track (TrackInline).

    Особенности:
    - Переход на NestedModelAdmin позволяет редактировать вложенные объекты
      прямо в форме альбома.
    """

    change_form_template = 'admin/store/album/change_form.html'

    class Media:
        """Подключает ресурсы формы альбома."""

        js = ('store/admin/album_track_upload.js',)

    list_display = (
        'name',
        'genre',
        'owner',
        'is_single',
        'is_published',
        'get_price',
        'get_allow_overpay',
        'visibility',
        'is_active',
    )
    search_fields = ('genre__name', 'name')
    list_filter = (
        'is_active',
        'created_at',
        'updated_at',
        'visibility',
    )
    ordering = ('-created_at', 'is_active', 'name')
    readonly_fields = (
        'image_preview',
        'created_at',
        'updated_at',
        'get_sku',
        'owner',
    )
    list_editable = ('is_active', 'is_published', 'visibility')
    fieldsets = (
        (
            'Основная информация',
            {
                'fields': (
                    'name',
                    'genre',
                    'is_single',
                    'release_date',
                    'description',
                    'cover_image',
                    'image_preview',
                    'is_published',
                    'visibility',
                    'get_sku',
                    'owner',
                    'is_active',
                ),
            },
        ),
        (
            'Системная информация',
            {
                'classes': ('collapse',),
                'fields': (
                    'created_at',
                    'updated_at',
                ),
            },
        ),
    )

    @admin.display(description='Изображение')
    def image_preview(self, obj):
        """Возвращает HTML-превью обложки альбома в списке админки."""
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="height:100px;border-radius:4px;">',
                obj.cover_image.url,
            )
        return '-'

    def get_queryset(self, request):
        """Родительский метод миксина + select_related('genre', 'owner')."""
        return super().get_queryset(request).select_related('genre', 'owner')

    def response_add(self, request, obj, post_url_continue=None):
        """Перенаправляет к загрузке треков после создания альбома."""
        if '_addtracks' in request.POST:
            return HttpResponseRedirect(
                reverse(
                    'admin:store_album_change',
                    args=(obj.pk,),
                ),
            )

        return super().response_add(
            request,
            obj,
            post_url_continue=post_url_continue,
        )

    def get_inlines(self, request, obj=None):
        """Возвращает inline-блоки для страницы альбома."""
        if obj is None:
            return (ProductInline,)

        return (
            ProductInline,
            AlbumArchiveInline,
            TrackInline,
        )

    def get_urls(self):
        """Добавляет внутренние URL для загрузки треков."""
        urls = super().get_urls()

        custom_urls = [
            path(
                '<int:album_id>/track-uploads/initiate/',
                self.admin_site.admin_view(self.initiate_track_upload),
                name='store_album_track_upload_initiate',
            ),
            path(
                'track-uploads/<int:upload_id>/file/',
                self.admin_site.admin_view(self.receive_track_upload_file),
                name='store_track_upload_receive_file',
            ),
            path(
                'track-uploads/<int:upload_id>/complete/',
                self.admin_site.admin_view(self.complete_track_upload),
                name='store_track_upload_complete',
            ),
        ]

        return custom_urls + urls

    def initiate_track_upload(self, request, album_id):
        """Создаёт черновой трек и попытку загрузки файла."""
        if request.method != 'POST':
            return JsonResponse(
                {
                    'detail': 'Метод не поддерживается.',
                },
                status=HTTPStatus.METHOD_NOT_ALLOWED,
            )

        album = self.get_object(request, str(album_id))

        if album is None:
            raise Http404('Альбом не найден.')

        if not self.has_change_permission(request, album):
            raise PermissionDenied

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {
                    'detail': 'Некорректный JSON.',
                },
                status=HTTPStatus.BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                track, upload = TrackUploadService.create_pending_track(
                    album=album,
                    filename=payload.get('filename', ''),
                    size=payload.get('size', 0),
                    content_type=payload.get('content_type', ''),
                )
                local_upload_url = reverse(
                    'admin:store_track_upload_receive_file',
                    args=(upload.pk,),
                )

                upload_instruction = (
                    TrackUploadTransportService.create_instruction(
                        upload=upload,
                        local_upload_url=local_upload_url,
                        local_upload_headers={
                            'X-CSRFToken': get_token(request),
                        },
                    )
                )
        except ValidationError as exc:
            return JsonResponse(
                {
                    'detail': exc.messages,
                },
                status=HTTPStatus.BAD_REQUEST,
            )
        except UploadTransportConfigurationError as exc:
            return JsonResponse(
                {
                    'detail': str(exc),
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )

        return JsonResponse(
            {
                'track': {
                    'id': track.pk,
                    'name': track.name,
                    'position': track.position,
                    'is_active': track.is_active,
                },
                'upload': {
                    'id': upload.pk,
                    'status': upload.status,
                    'expires_at': upload_instruction.expires_at.isoformat(),
                    'complete_url': reverse(
                        'admin:store_track_upload_complete',
                        args=(upload.pk,),
                    ),
                    'transport': {
                        'method': upload_instruction.method,
                        'url': upload_instruction.url,
                        'headers': upload_instruction.headers,
                        'fields': upload_instruction.fields,
                        'file_field_name': (
                            upload_instruction.file_field_name
                        ),
                    },
                },
            },
            status=HTTPStatus.CREATED,
        )

    def receive_track_upload_file(self, request, upload_id):
        """Принимает файл в локальном режиме разработки."""
        if request.method != 'POST':
            return JsonResponse(
                {
                    'detail': 'Метод не поддерживается.',
                },
                status=HTTPStatus.METHOD_NOT_ALLOWED,
            )

        if settings.USE_S3_MEDIA:
            raise Http404

        try:
            upload = TrackUpload.objects.select_related('track__album').get(
                pk=upload_id,
            )
        except TrackUpload.DoesNotExist as exc:
            raise Http404('Попытка загрузки не найдена.') from exc

        album = upload.track.album

        if not self.has_change_permission(request, album):
            raise PermissionDenied

        uploaded_file = request.FILES.get('file')

        if uploaded_file is None:
            return JsonResponse(
                {
                    'detail': 'Не передан файл.',
                },
                status=HTTPStatus.BAD_REQUEST,
            )

        try:
            upload = TrackUploadService.receive_local_file(
                upload=upload,
                uploaded_file=uploaded_file,
            )
        except ValidationError as exc:
            return JsonResponse(
                {
                    'detail': exc.messages,
                },
                status=HTTPStatus.BAD_REQUEST,
            )

        return JsonResponse(
            {
                'upload': {
                    'id': upload.pk,
                    'status': upload.status,
                    'uploaded_size': upload.uploaded_size,
                },
            },
            status=HTTPStatus.OK,
        )

    def complete_track_upload(self, request, upload_id):
        """Подтверждает загрузку файла и запускает подготовку аудио."""
        if request.method != 'POST':
            return JsonResponse(
                {
                    'detail': 'Метод не поддерживается.',
                },
                status=HTTPStatus.METHOD_NOT_ALLOWED,
            )

        try:
            upload = TrackUpload.objects.select_related('track__album').get(
                pk=upload_id,
            )
        except TrackUpload.DoesNotExist as exc:
            raise Http404('Попытка загрузки не найдена.') from exc

        album = upload.track.album

        if not self.has_change_permission(request, album):
            raise PermissionDenied

        try:
            upload = TrackUploadStorageService.complete(
                upload=upload,
            )
        except TrackUploadStorageError as exc:
            return JsonResponse(
                {
                    'detail': str(exc),
                },
                status=HTTPStatus.BAD_REQUEST,
            )

        return JsonResponse(
            {
                'track': {
                    'id': upload.track_id,
                    'name': upload.track.name,
                    'position': upload.track.position,
                    'is_active': upload.track.is_active,
                },
                'upload': {
                    'id': upload.pk,
                    'status': upload.status,
                    'uploaded_size': upload.uploaded_size,
                    'completed_at': upload.completed_at.isoformat(),
                },
            },
            status=HTTPStatus.OK,
        )
