from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Case, F, Q, QuerySet, Value, When

from store.models import CatalogSearch


class CatalogSearchService:
    """Поиск по глобальному каталогу."""

    @staticmethod
    def search(query: str) -> QuerySet[CatalogSearch]:
        """Возвращает результаты глобального поиска."""
        query = query.strip()

        if not query:
            return CatalogSearch.objects.none()

        search_query = SearchQuery(query, config='simple')

        qs = CatalogSearch.objects.filter(
            Q(search_vector=search_query)
            | Q(search_text__trigram_word_similar=query),
        )

        if settings.PUBLICATION_READINESS_ENABLED:
            qs = qs.filter(
                Q(is_publication_ready=True)
                | Q(is_publication_ready__isnull=True),
            )

        return qs.annotate(
            fts_rank=SearchRank(F('search_vector'), search_query),
            has_fts=Case(
                When(search_vector=search_query, then=Value(1)),
                default=Value(0),
            ),
        ).order_by(
            '-has_fts',
            '-fts_rank',
            'entity_type',
            'name',
        )
