import django_filters


class ArtistReportFilter(django_filters.FilterSet):
    """Фильтр отчетов артиста по периоду и типу."""

    date_from = django_filters.DateFilter(
        method='filter_period',
        label='С',
    )
    date_to = django_filters.DateFilter(
        method='filter_period',
        label='По',
    )

    def filter_period(self, queryset, name, value):
        """Фильтрует отчеты по пересечению периода с диапазоном дат."""
        date_from = self.data.get('date_from')
        date_to = self.data.get('date_to')

        if date_from:
            queryset = queryset.filter(
                period_end__gte=date_from,
            )

        if date_to:
            queryset = queryset.filter(
                period_start__lte=date_to,
            )

        return queryset
