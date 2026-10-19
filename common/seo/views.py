from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.services import artist_publication_ready_q

from .schema import sitemap_schema
from .serializers import SitemapEntrySerializer
from store.models import Product
from users.models import ArtistProfile


@method_decorator(cache_page(60 * 60), name='dispatch')
@sitemap_schema
class SitemapDataView(APIView):
    """Данные для сборки sitemap.xml на фронтенде.

    Состав совпадает с публичным каталогом: используются те же
    методы ProductQuerySet, без превью черновиков.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request):
        """Возвращает список публичных страниц."""
        entries = []

        # Релизы. Страницы носителей ведут на релиз, отдельных записей нет.
        releases = Product.objects.published_albums().values(
            'album_id',
            'album__updated_at',
        )
        for row in releases:
            entries.append({
                'type': 'release',
                'id': row['album_id'],
                'slug': None,
                'lastmod': row['album__updated_at'],
            })

        # Обычный мерч. Носители с альбомом уже учтены как релизы.
        merch = (
            Product.objects
            .published_merch()
            .exclude(
                merch__kind__is_carrier=True,
                merch__album_id__isnull=False,
            )
            .values('merch_id', 'merch__updated_at')
        )
        for row in merch:
            entries.append({
                'type': 'merch',
                'id': row['merch_id'],
                'slug': None,
                'lastmod': row['merch__updated_at'],
            })

        # Артисты
        artists = (
            ArtistProfile.objects
            .filter(artist_publication_ready_q(), is_active=True)
            .exclude(slug='')
            .values('slug', 'updated_at')
        )
        for row in artists:
            entries.append({
                'type': 'artist',
                'id': None,
                'slug': row['slug'],
                'lastmod': row['updated_at'],
            })

        serializer = SitemapEntrySerializer(entries, many=True)
        return Response(serializer.data)
