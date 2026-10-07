from store.services import get_track_sales_stats


class TrackDeactivationProtectionMixin:
    """Запрещает деактивацию трека с историей приобретения."""

    def clean(self):
        cleaned_data = super().clean()

        if (
            self.instance.pk
            and self.instance.is_active
            and cleaned_data.get('is_active') is False
        ):
            sales = get_track_sales_stats(self.instance)

            if sales.total_sales:
                self.add_error(
                    'is_active',
                    (
                        'Нельзя деактивировать трек с историей приобретения. '
                        f'Трек куплен отдельно: {sales.direct_sales} раз; '
                        f'в составе релиза: {sales.release_sales} раз. '
                        'Чтобы изменить состав, снимите текущий релиз '
                        'с продажи и создайте новый без этого трека.'
                    ),
                )

        return cleaned_data
