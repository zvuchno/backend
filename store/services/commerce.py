"""Модуль бизнес-логики управления коммерческой инфраструктурой контента."""

from django.apps import apps
from django.db import transaction

from store.constants import CHAR_PRESET_DIGITAL, CHAR_PRESET_SIMPLE
from store.models import Product


class ProductService:
    """Сервис для управления коммерческой логикой контента.

    Обеспечивает централизованное создание и синхронизацию связанных
    сущностей (Product, ProductVariant) для различных типов контента.
    """

    @staticmethod
    @transaction.atomic()
    def ensure_commerce(content_instance) -> Product:
        """Гарантирует наличие связанных объектов Product и ProductVariant.

        Не изменяет существующие объекты.
        """
        model_name = content_instance.__class__.__name__.lower()
        # Импорт через apps, чтобы избежать циклической зависимости
        Product = apps.get_model('store', 'Product')

        try:
            product = content_instance.product
        except Product.DoesNotExist:
            product = Product.objects.create(**{model_name: content_instance})

        if not product.variants.exists():
            if model_name in ['album', 'track']:
                product.variants.create(
                    product=product,
                    property_value=CHAR_PRESET_DIGITAL,
                    stock=None,  # Для цифры склад не нужен
                    is_active=True,
                )
        return product

    @staticmethod
    @transaction.atomic()
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
            ProductVariant = apps.get_model('store', 'ProductVariant')
            incoming_ids = []

            for variant_data in variants_data:
                variant_id = variant_data.get('id')
                variant_value = variant_data.get('property_value')

                # Если ID пришел — ищем по нему (приоритет).
                # Если нет — по значению (защита от дублей).
                lookup = (
                    {'id': variant_id}
                    if variant_id
                    else {'property_value': variant_value, 'product': product}
                )

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
