from django.apps import AppConfig


class CatalogMigrationConfig(AppConfig):
    """Конфигурация приложения разовой миграции каталога."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'catalog_migration'
    verbose_name = 'Миграция каталога'
