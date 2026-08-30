from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Case, F, Q, QuerySet, Value, When

from store.models import CatalogSearch

ENTITY_TYPE_PRIORITY = {
    CatalogSearch.EntityType.ARTIST: 1,
    CatalogSearch.EntityType.ALBUM: 2,
    CatalogSearch.EntityType.TRACK: 3,
    CatalogSearch.EntityType.MERCH: 4,
}


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

        entity_priority = Case(
            *(
                When(
                    entity_type=entity_type,
                    then=Value(priority),
                )
                for entity_type, priority in ENTITY_TYPE_PRIORITY.items()
            ),
            default=Value(99),
        )

        return qs.annotate(
            fts_rank=SearchRank(
                F('search_vector'),
                search_query,
            ),
            has_fts=Case(
                When(
                    search_vector=search_query,
                    then=Value(1),
                ),
                default=Value(0),
            ),
            entity_priority=entity_priority,
        ).order_by(
            'entity_priority',
            '-has_fts',
            '-fts_rank',
            'name',
        )
