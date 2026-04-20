"""Модуль бизнес-логики управления коммерческой инфраструктурой контента."""

from django.apps import apps
from django.db import transaction

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
        ProductVariant = apps.get_model('store', 'ProductVariant')

        try:
            product = content_instance.product
        except Product.DoesNotExist:
            product = Product.objects.create(**{model_name: content_instance})

        if not product.variants.exists():
            if model_name in ['album', 'track']:
                ProductVariant.objects.create(
                    product=product,
                    characteristic={'format': 'digital'},
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
            characteristic = {'type': 'simple'}
            # Ищем базовый вариант (даже неактивный)
            variant = product.variants.filter(
                characteristic=characteristic,
            ).first()

            if not variant:
                # Создаем новый, если такого типа никогда не было
                ProductVariant = apps.get_model('store', 'ProductVariant')
                variant = ProductVariant.objects.create(
                    product=product,
                    characteristic=characteristic,
                    stock=stock,
                    is_active=True,
                )
            else:
                # Если нашли старый — реанимируем и обновляем сток
                variant.stock = stock
                variant.is_active = True
                variant.save(
                    update_fields=['stock', 'is_active', 'characteristic'],
                )
            # Выключаем все остальные варианты этого продукта
            product.variants.exclude(id=variant.id).update(is_active=False)
        else:
            # Сценарий 2: Есть свойства -> создаем по варианту на каждое
            ProductVariant = apps.get_model('store', 'ProductVariant')
            incoming_ids = []

            for opt in variants_data:
                v_id = opt.get('id')

                if v_id:
                    # Если ID пришел, обновляем существующий вариант
                    ProductVariant.objects.filter(
                        id=v_id,
                        product=product,
                    ).update(
                        stock=opt.get('stock', 0),
                        characteristic=opt.get('characteristic', {}),
                        is_active=True,
                    )
                    incoming_ids.append(v_id)
                else:
                    # Если ID нет, создаем новый
                    new_v = ProductVariant.objects.create(
                        product=product,
                        stock=opt.get('stock', 0),
                        characteristic=opt.get('characteristic', {}),
                        is_active=True,
                    )
                    incoming_ids.append(new_v.id)

            # Деактивируем все варианты, которые не пришли в запросе
            product.variants.exclude(id__in=incoming_ids).update(
                is_active=False,
            )
