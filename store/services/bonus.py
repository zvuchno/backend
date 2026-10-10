"""Сервисы для работы с бонусами."""

from django.db import transaction
from rest_framework import serializers

from store.models import Bonus


def reorder_bonuses(album, bonus_ids):
    """Атомарно расставляет позиции бонусов по порядку списка."""
    with transaction.atomic():
        bonuses = Bonus.objects.select_for_update().filter(
            album=album,
            is_active=True,
        )
        by_id = {bonus.pk: bonus for bonus in bonuses}

        if set(bonus_ids) != by_id.keys():
            raise serializers.ValidationError(
                {
                    'bonus_ids': 'Нужно передать все бонусы'
                    'альбома по одному разу.',
                },
            )

        for position, bonus_id in enumerate(bonus_ids, start=1):
            by_id[bonus_id].position = position

        Bonus.objects.bulk_update(by_id.values(), ['position'])
