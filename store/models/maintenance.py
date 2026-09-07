from store.models.album import Album


class MaintenanceOperations(Album):
    """Технический proxy для сервисного раздела админки."""

    class Meta:
        proxy = True
        verbose_name = 'сервисная операция'
        verbose_name_plural = 'сервисные операции'
