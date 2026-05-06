"""Сериализатор избранного пользователя."""

from rest_framework import serializers

from store.models import Favorite


class FavoritesSerializer(serializers.ModelSerializer):
    """Сериализатор модели Favorite."""

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    target_url = serializers.CharField(
        source='product_variant.product.target_url',
        read_only=True,
    )

    class Meta:
        model = Favorite
        fields = ('id', 'user', 'product_variant', 'target_url')
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=Favorite.objects.all(),
                fields=['user', 'product_variant'],
                message='Этот товар уже в вашем избранном.',
            ),
        ]
