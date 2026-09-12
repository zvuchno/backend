from django.db import transaction
from rest_framework import serializers

from users.models import (
    ArtistPickupPoint,
    ArtistShippingPoint,
    ArtistStoreSettings,
)


class ArtistShippingPointSerializer(serializers.ModelSerializer):
    """Сериализатор ПВЗ СДЭК для отправки заказов артиста."""

    class Meta:
        model = ArtistShippingPoint
        fields = (
            'pvz_code',
            'city_code',
            'city',
            'address',
        )


class ArtistShippingSettingsSerializer(serializers.Serializer):
    """Настройки доставки СДЭК."""

    enabled = serializers.BooleanField(required=False)
    point = ArtistShippingPointSerializer(
        required=False,
    )

    def validate(self, attrs):
        """Проверяет возможность включения СДЭК."""
        attrs = super().validate(attrs)

        requested_enabled = attrs.get('enabled')

        if requested_enabled is not True:
            return attrs

        point_data = attrs.get('point')

        if point_data is not None:
            return attrs

        shipping_point = getattr(
            self.instance,
            'shipping_point',
            None,
        )

        if shipping_point is None or not shipping_point.is_configured:
            raise serializers.ValidationError({
                'enabled': 'Для включения СДЭК укажите ПВЗ.',
            })

        return attrs

    @transaction.atomic
    def update(self, artist, validated_data):
        """Сохраняет ПВЗ и состояние СДЭК."""
        point_data = validated_data.get('point')
        requested_enabled = validated_data.get('enabled')

        if point_data is not None:
            ArtistShippingPoint.objects.update_or_create(
                artist=artist,
                defaults=point_data,
            )

        if requested_enabled is not None:
            settings, _ = ArtistStoreSettings.objects.get_or_create(
                artist=artist,
            )
            settings.shipping_enabled = requested_enabled
            settings.save(
                update_fields=('shipping_enabled',),
            )

        return artist

    def to_representation(self, artist):
        """Возвращает ПВЗ и состояние СДЭК."""
        settings = getattr(artist, 'store_settings', None)
        point = getattr(artist, 'shipping_point', None)

        return {
            'enabled': bool(
                settings and settings.shipping_enabled,
            ),
            'point': (
                ArtistShippingPointSerializer(point).data if point else None
            ),
        }


class ArtistPickupPointSettingsSerializer(serializers.ModelSerializer):
    """Изменение точки самовывоза в общем запросе настроек."""

    id = serializers.IntegerField(required=False)

    class Meta:
        model = ArtistPickupPoint
        fields = (
            'id',
            'address',
            'pickup_date',
            'is_active',
        )
        extra_kwargs = {
            'address': {'required': False},
            'pickup_date': {'required': False},
            'is_active': {'required': False},
        }


class ArtistPickupSettingsSerializer(serializers.Serializer):
    """Настройки самовывоза."""

    enabled = serializers.BooleanField(required=False)
    points = ArtistPickupPointSettingsSerializer(
        many=True,
        required=False,
    )

    def validate(self, attrs):
        """Проверяет итоговое состояние самовывоза."""
        attrs = super().validate(attrs)

        artist = self.instance
        points_data = attrs.get('points', [])

        existing_points = {
            point.id: point for point in artist.pickup_points.all()
        }

        changes, new_points = self._split_point_changes(
            points_data,
            existing_points,
        )

        has_active_points = self._validate_active_points(
            existing_points,
            changes,
            new_points,
        )

        requested_enabled = attrs.get('enabled')

        if requested_enabled is True and not has_active_points:
            raise serializers.ValidationError({
                'enabled': (
                    'Для включения самовывоза нужна '
                    'хотя бы одна активная точка.'
                ),
            })

        attrs['_has_active_points'] = has_active_points

        return attrs

    @staticmethod
    def _split_point_changes(
        points_data,
        existing_points,
    ) -> tuple[dict, list]:
        """Разделяет новые точки и изменения существующих."""
        changes = {}
        new_points = []

        for point_data in points_data:
            point_id = point_data.get('id')

            if point_id is None:
                if not point_data.get('address'):
                    raise serializers.ValidationError({
                        'points': 'Для новой точки укажите адрес.',
                    })

                new_points.append(point_data)
                continue

            if point_id not in existing_points:
                raise serializers.ValidationError({
                    'points': ('Указана точка самовывоза другого профиля.'),
                })

            if point_id in changes:
                raise serializers.ValidationError({
                    'points': 'Одна точка передана несколько раз.',
                })

            changes[point_id] = point_data

        return changes, new_points

    @staticmethod
    def _validate_active_points(
        existing_points,
        changes,
        new_points,
    ) -> bool:
        """Проверяет активные точки и отсутствие дублей."""
        active_keys = set()
        has_active_points = False

        for point_id, point in existing_points.items():
            change = changes.get(point_id, {})

            if not change.get('is_active', point.is_active):
                continue

            key = (
                change.get('address', point.address),
                change.get('pickup_date', point.pickup_date),
            )

            if key in active_keys:
                raise serializers.ValidationError({
                    'points': (
                        'Активные точки самовывоза не должны дублироваться.'
                    ),
                })

            active_keys.add(key)
            has_active_points = True

        for point_data in new_points:
            if not point_data.get('is_active', True):
                continue

            key = (
                point_data['address'],
                point_data.get('pickup_date'),
            )

            if key in active_keys:
                raise serializers.ValidationError({
                    'points': (
                        'Активные точки самовывоза не должны дублироваться.'
                    ),
                })

            active_keys.add(key)
            has_active_points = True

        return has_active_points

    @transaction.atomic
    def update(self, artist, validated_data):
        """Сохраняет изменения точек и состояние самовывоза."""
        has_active_points = validated_data.pop('_has_active_points')
        requested_enabled = validated_data.get('enabled')
        points_data = validated_data.get('points', [])

        for point_data in points_data:
            point_id = point_data.pop('id', None)

            if point_id is None:
                ArtistPickupPoint.objects.create(
                    artist=artist,
                    **point_data,
                )
                continue

            pickup_point = artist.pickup_points.get(
                pk=point_id,
            )

            for field, value in point_data.items():
                setattr(pickup_point, field, value)

            pickup_point.save()

        if not has_active_points:
            ArtistStoreSettings.objects.filter(
                artist=artist,
                pickup_enabled=True,
            ).update(
                pickup_enabled=False,
            )
        elif requested_enabled is not None:
            settings, _ = ArtistStoreSettings.objects.get_or_create(
                artist=artist,
            )
            settings.pickup_enabled = requested_enabled
            settings.save(
                update_fields=('pickup_enabled',),
            )

        return artist

    def to_representation(self, artist):
        """Возвращает активные точки и состояние самовывоза."""
        settings = getattr(artist, 'store_settings', None)
        points = artist.pickup_points.filter(
            is_active=True,
        ).order_by('id')

        return {
            'enabled': bool(settings and settings.pickup_enabled),
            'points': ArtistPickupPointSettingsSerializer(
                points,
                many=True,
            ).data,
        }
