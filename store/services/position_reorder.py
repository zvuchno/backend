"""Сервис для изменения порядка объектов."""

from django.db import transaction
from rest_framework import serializers


def reorder_objects(queryset, object_ids, ids_field):
    """Атомарно изменяет порядок объектов."""
    with transaction.atomic():
        objects = queryset.select_for_update(of=('self',))
        by_id = {obj.pk: obj for obj in objects}

        if len(object_ids) != len(by_id) or set(object_ids) != by_id.keys():
            raise serializers.ValidationError(
                {
                    ids_field: (
                        'Нужно передать все объекты списка по одному разу.'
                    ),
                },
            )

        for position, object_id in enumerate(object_ids, start=1):
            by_id[object_id].position = position

        queryset.model.objects.bulk_update(
            by_id.values(),
            ['position'],
        )
