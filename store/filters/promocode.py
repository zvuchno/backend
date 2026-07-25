import django_filters
from django.db.models import F, Q
from django.utils import timezone

from store.models import Promocode


class PromoCodeFilter(django_filters.FilterSet):
    """Набор фильтров для модели Промокодов."""

    discount_type = django_filters.ChoiceFilter(
        field_name='discount_type',
        choices=Promocode.DiscountType.choices,
    )
    is_available = django_filters.BooleanFilter(
        method='filter_is_available',
        label='Доступен для использования',
    )

    class Meta:
        model = Promocode
        fields = ['discount_type', 'is_available']

    def filter_is_available(self, queryset, name, value):
        now = timezone.now()

        available_condition = (
            Q(is_active=True)
            & Q(is_enabled=True)
            & (Q(start_at__isnull=True) | Q(start_at__lte=now))
            & (Q(end_at__isnull=True) | Q(end_at__gte=now))
            & (
                Q(usage_limit__isnull=True)
                | Q(used_count__lt=F('usage_limit'))
            )
        )

        if value is True:
            return queryset.filter(available_condition)
        if value is False:
            return queryset.exclude(available_condition)

        return queryset
