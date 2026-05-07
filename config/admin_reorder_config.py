"""Конфигурация группировки и порядка приложений и моделей в Django admin.

Используется библиотека django-modeladmin-reorder (fork).

ВАЖНО:
- Библиотека полностью переопределяет порядок отображения разделов admin.
- Отображаются только те apps, которые указаны в ADMIN_REORDER.
- Если приложение не указано — оно НЕ появится в /admin/.

Формат:
1) Строка — оставить приложение без изменений (Django сам сгруппирует модели)
2) dict — кастомная группа моделей внутри приложения

Принцип работы:
- Django сначала регистрирует все модели
- затем middleware reorder формирует новый список разделов админки
- порядок и группировка полностью задаются здесь

Как добавлять новое приложение:
- если нужно просто показать app → добавить строкой: 'app_label'
- если нужно разбить на группы → используйте dict с 'app', 'label', 'models'
"""

ADMIN_REORDER = (
    {
        'app': 'store',
        'label': 'Витрина',
        'models': (
            'store.Album',
            'store.Track',
            'store.Merch',
            'store.Genre',
            'store.MerchKind',
        ),
    },
    {
        'app': 'store',
        'label': 'Заказы',
        'models': (
            'store.Order',
            'store.Cart',
            'store.Delivery',
            'store.Favorite',
        ),
    },
    # Объединяем пользователей (users) и системные права доступа (auth)
    # в один раздел админки для удобного управления аккаунтами и ролями
    {
        'app': 'users',
        'label': 'Пользователи и доступы',
        'models': (
            'users.CoreUser',
            'users.ListenerProfile',
            'users.ArtistProfile',
            'auth.Group',
            'auth.Permission',
        ),
    },
    # Sites framework (django.contrib.sites)
    'sites',
    # Социальная авторизация (social accounts + providers)
    'socialaccount',
    {
        'app': 'users',
        'label': 'Документы и согласия',
        'models': (
            'users.DocumentType',
            'users.ConsentDocument',
            'users.UserConsent',
        ),
    },
)
