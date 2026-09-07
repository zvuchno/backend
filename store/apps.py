from django.apps import AppConfig


class StoreConfig(AppConfig):
    """TODO."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'
    verbose_name = 'Витрина'

    def ready(self) -> None:
        """Подключает обработчики сигналов приложения."""
        import store.signals  # noqa
