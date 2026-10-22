from rest_framework import serializers


class SitemapEntrySerializer(serializers.Serializer):
    """Запись для sitemap. URL собирает фронтенд по type + id/slug."""

    type = serializers.CharField(
        help_text='Тип страницы: release, merch или artist.',
    )
    id = serializers.IntegerField(
        allow_null=True,
        help_text=(
            'ID релиза (Album) или мерча (Merch), как в target.id '
            'карточки каталога. Для artist равен null.'
        ),
    )
    slug = serializers.CharField(
        allow_null=True,
        help_text='Slug профиля артиста. Для release и merch равен null.',
    )
    lastmod = serializers.DateTimeField(
        help_text='Дата последнего изменения страницы.',
    )
