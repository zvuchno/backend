"""Модуль бизнес-логики управления коммерческой инфраструктурой контента."""

from django.db import transaction

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

        # Если продукт уже был — обновляем его поля
        if not created:
            cls._update_product_base_fields(product, validated_data)

        # Для альбомов и треков гарантируем наличие цифрового варианта
        if model_name in ['album', 'track']:
            cls._ensure_digital_variant(product)

        # Варианты мерча синхронизируем всегда
        if model_name == 'merch':
            cls.sync_merch_variants(
                product=product,
                stock=validated_data.get('stock', 0),
                variants_data=validated_data.get('variants'),
            )

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
    def sync_merch_variants(product, stock, variants_data=None) -> None:
        """Синхронизирует варианты мерча на основе переданных данных."""
        if not variants_data:
            # Сценарий 1: Свойств нет -> один вариант с общим стоком
            variant, _ = product.variants.update_or_create(
                property_value=CHAR_PRESET_SIMPLE,
                defaults={
                    'stock': stock,
                    'is_active': True,
                },
            )
            # Выключаем всё остальное
            product.variants.exclude(id=variant.id).update(is_active=False)
        else:
            # Сценарий 2: Есть свойства -> создаем по варианту на каждое
            incoming_ids = []

            for variant_data in variants_data:
                variant_id = variant_data.get('id')
                variant_value = variant_data.get('property_value')

                lookup = {'product': product}
                # Если ID пришел — ищем по нему (приоритет).
                if variant_id:
                    # Проверяем, существует ли такой ID у этого продукта
                    if product.variants.filter(id=variant_id).exists():
                        lookup['id'] = variant_id
                    else:
                        # Если ID чужой — игнорируем его и ищем по значению
                        lookup['property_value'] = variant_value
                else:
                    lookup['property_value'] = variant_value

                variant, _ = ProductVariant.objects.update_or_create(
                    **lookup,
                    defaults={
                        'property_value': variant_value,
                        'stock': variant_data.get('stock', 0),
                        'is_active': True,
                    },
                )
                incoming_ids.append(variant.id)

            # Деактивируем варианты, которых нет в новом списке
            product.variants.exclude(
                id__in=incoming_ids,
            ).update(is_active=False)
