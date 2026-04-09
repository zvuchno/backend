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
            variant_data = {'product': product}
            if model_name != 'merch':
                variant_data.update({
                    'characteristic': {'format': 'digital'},
                    'stock': None,  # Для цифры склад не нужен
                })
            ProductVariant.objects.create(**variant_data)

        return product
