"""Модуль бизнес-логики управления коммерческой инфраструктурой контента."""

from django.db import transaction
from rest_framework.exceptions import ValidationError

from store.constants import CHAR_PRESET_DIGITAL, CHAR_PRESET_SIMPLE
from store.models import Product, ProductVariant


class ProductService:
    """Сервис для управления коммерческой логикой контента.

    Обеспечивает централизованное создание и синхронизацию связанных
    сущностей (Product, ProductVariant) для различных типов контента.
    """

    @classmethod
    @transaction.atomic
    def ensure_commerce(cls, content_instance, validated_data) -> Product:
        model_name = content_instance.__class__.__name__.lower()

        defaults = {
            'price': validated_data.get('price', 0),
            'allow_overpay': validated_data.get('allow_overpay', False),
            'property_name': validated_data.get('property_name', ''),
        }

        product, created = Product.objects.get_or_create(
            **{model_name: content_instance},
            defaults=defaults,
        )

        # Если продукт уже был → обновляем его поля
        if not created:
            cls._update_product_base_fields(product, validated_data)

        # Для альбомов и треков гарантируем наличие цифрового варианта
        if model_name in ['album', 'track']:
            cls._ensure_digital_variant(product)

        # Варианты мерча синхронизируем всегда
        if model_name == 'merch':
            if 'variants' in validated_data:
                # POST/PATCH и 'variants' в запросе
                cls.sync_merch_variants(
                    product=product,
                    value_stock=validated_data.get('stock', 0),
                    variants_data=validated_data.get('variants'),
                )
            elif created:
                # POST без variants → создаём simple
                cls.sync_merch_variants(
                    product=product,
                    value_stock=validated_data.get('stock', 0),
                    variants_data=None,
                )
            has_active_variants = (
                product.variants
                .filter(
                    is_active=True,
                )
                .exclude(
                    property_value=CHAR_PRESET_SIMPLE,
                )
                .exists()
            )

            if not has_active_variants and product.property_name:
                product.property_name = ''
                product.save(update_fields=['property_name'])

        return product

    @staticmethod
    def _ensure_digital_variant(product) -> None:
        """Создает вариант цифрового товара."""
        product.variants.get_or_create(
            property_value=CHAR_PRESET_DIGITAL,
            defaults={
                'stock': None,  # Для цифры склад не нужен
                'is_active': True,
            },
        )

    @staticmethod
    def _update_product_base_fields(product, validated_data) -> None:
        """Обновляет поля Product, если они изменились."""
        allowed_fields = ['price', 'allow_overpay', 'property_name']
        updated_fields = []

        for key in allowed_fields:
            if key in validated_data:
                value = validated_data[key]
                if getattr(product, key) != value:
                    setattr(product, key, value)
                    updated_fields.append(key)

        if updated_fields:
            product.save(update_fields=updated_fields)

    @staticmethod
    @transaction.atomic
    def sync_merch_variants(product, value_stock, variants_data=None) -> None:
        """Синхронизирует варианты мерча на основе переданных данных."""
        if not variants_data:
            # Сценарий 1: Свойств нет -> один вариант с общим стоком
            variant, _ = product.variants.update_or_create(
                property_value=CHAR_PRESET_SIMPLE,
                defaults={
                    'stock': value_stock,
                    'is_active': True,
                },
            )
            # Выключаем всё остальное
            product.variants.exclude(id=variant.id).update(is_active=False)
        else:
            # Сценарий 2: Есть свойства -> создаем по варианту на каждое
            incoming_ids = []
            seen_values = set()
            existing_v_ids = set(product.variants.values_list('id', flat=True))

            for variant_data in variants_data:
                variant_id = variant_data.get('id')
                value = variant_data.get('property_value')
                stock = variant_data.get('stock')
                is_active = variant_data.get('is_active', True)

                #  =============== Валидация ===============
                if (
                    value is None
                    or str(value).strip() == ''
                    or not isinstance(stock, int)
                    or stock < 0
                ):
                    raise ValidationError({
                        'variants': 'value и stock — обязательны '
                        'для свойства (stock должен быть числом).',
                    })

                variant_value = str(value).strip()

                if variant_value in seen_values:
                    raise ValidationError({
                        'variants': 'В запросе дублирующиеся '
                        'значения вариантов.',
                    })
                seen_values.add(variant_value)

                duplicate_qs = ProductVariant.objects.filter(
                    product=product,
                    property_value=variant_value,
                )
                if variant_id:
                    # Проверка принадлежности продукту
                    if variant_id not in existing_v_ids:
                        raise ValidationError({
                            'variants': f'Вариант с ID {variant_id} '
                            'не принадлежит данному продукту.',
                        })
                    # Если редактируем существующий — исключаем его самого
                    duplicate_qs = duplicate_qs.exclude(id=variant_id)

                    if duplicate_qs.exists():
                        raise ValidationError({
                            'variants': (
                                'Нельзя переименовать вариант со значением '
                                f'{variant_value}, он уже существует '
                                'у этого товара. Добавьте его, если '
                                'снова хотите активировать.'
                            ),
                        })

                # =============== Синхронизация ===============
                lookup = {'product': product}
                # Если ID пришел — ищем по нему (приоритет)
                if variant_id:
                    lookup['id'] = variant_id
                else:
                    # Если ID нет — ищем по значению (защита от дублей)
                    lookup['property_value'] = variant_value

                variant, _ = ProductVariant.objects.update_or_create(
                    **lookup,
                    defaults={
                        'property_value': variant_value,
                        'stock': stock,
                        'is_active': is_active,
                    },
                )
                incoming_ids.append(variant.id)

            # Деактивируем варианты, которых нет в новом списке
            product.variants.exclude(
                id__in=incoming_ids,
            ).update(is_active=False)
