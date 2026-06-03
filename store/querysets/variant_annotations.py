"""Переиспользуемые фабрики аннотаций для ProductVariant и связанных моделей.

Содержит фабрики ORM-аннотаций, используемые в ProductVariant,
CartItem, OrderItem и других моделях, работающих с вариантами товаров.
"""

from django.db import models
from django.db.models import Case, F, IntegerField, Value, When
from django.db.models.functions import Coalesce


def build_target_annotations(product_path: str) -> dict:
    """Создаёт аннотации для формирования карточки перехода.

    Добавляет вычисляемые поля:
        - is_carrier — является ли мерч физическим носителем;
        - artist_name — имя артиста-владельца товара;
        - kind — человекочитаемый тип карточки
          (Альбом, Сингл, Трек, Винил и т.п.);
        - target_type — тип целевого объекта для перехода;
        - target_id — идентификатор целевого объекта для перехода.

    Args:
        product_path: ORM-путь до модели Product относительно
            аннотируемого QuerySet'а.

            Примеры:
                'product'
                'product_variant__product'
    Returns:
        Словарь ORM-выражений для передачи в QuerySet.annotate().

    """
    carrier_album_condition = {
        f'{product_path}__product_type': 'merch',
        f'{product_path}__merch__kind__is_carrier': True,
        f'{product_path}__merch__album_id__isnull': False,
    }

    return {
        'is_carrier': Coalesce(
            F(f'{product_path}__merch__kind__is_carrier'),
            Value(False),
        ),
        'artist_name': Coalesce(
            F(f'{product_path}__album__owner__artist_profile__name'),
            F(f'{product_path}__track__owner__artist_profile__name'),
            F(f'{product_path}__merch__owner__artist_profile__name'),
        ),
        'kind': Case(
            When(
                **{
                    f'{product_path}__product_type': 'album',
                    f'{product_path}__album__is_single': True,
                },
                then=Value('Сингл'),
            ),
            When(
                **{
                    f'{product_path}__product_type': 'album',
                    f'{product_path}__album__is_single': False,
                },
                then=Value('Альбом'),
            ),
            When(
                **{f'{product_path}__product_type': 'track'},
                then=Value('Трек'),
            ),
            When(
                **{f'{product_path}__product_type': 'merch'},
                then=F(f'{product_path}__merch__kind__name'),
            ),
            output_field=models.CharField(),
        ),
        'target_type': Case(
            When(
                **carrier_album_condition,
                then=Value('album'),
            ),
            When(
                **{f'{product_path}__product_type': 'track'},
                then=Value('album'),
            ),
            default=F(f'{product_path}__product_type'),
            output_field=models.CharField(),
        ),
        'target_id': Case(
            When(
                **carrier_album_condition,
                then=F(f'{product_path}__merch__album_id'),
            ),
            When(
                **{f'{product_path}__product_type': 'album'},
                then=F(f'{product_path}__album_id'),
            ),
            When(
                **{f'{product_path}__product_type': 'merch'},
                then=F(f'{product_path}__merch_id'),
            ),
            When(
                **{f'{product_path}__product_type': 'track'},
                then=F(f'{product_path}__track__album_id'),
            ),
            output_field=IntegerField(),
        ),
    }
