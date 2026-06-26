import json

from django.contrib import admin
from django.contrib.admin.models import LogEntry


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """Админ-панель для отображения логов действий пользователей.

    Класс предоставляет:
    - Читаемый интерфейс для просмотра истории изменений объектов.
    - Фильтрацию по типу действия, пользователю и типу модели.
    - Поиск по описанию и имени пользователя.
    - Парсинг JSON-сообщений в читаемый вид.
    """

    list_display = [
        'action_time',
        'user',
        'get_content_type',
        'object_repr',
        'action_flag_display',
        'parsed_change_message',
    ]
    list_filter = ['action_flag', 'content_type', 'user']
    search_fields = ['object_repr', 'change_message', 'user__username']
    date_hierarchy = 'action_time'
    readonly_fields = [
        'action_time',
        'user',
        'content_type',
        'object_id',
        'object_repr',
        'action_flag',
        'change_message',
    ]
    list_select_related = ('user', 'content_type')

    def get_content_type(self, obj):
        return obj.content_type.name

    get_content_type.short_description = 'Тип объекта'

    def action_flag_display(self, obj):
        flags = {1: 'Создание', 2: 'Изменение', 3: 'Удаление'}
        return flags.get(obj.action_flag, 'Неизвестно')

    action_flag_display.short_description = 'Действие'

    def _format_item(self, item) -> str:
        """Вспомогательный метод для обработки одного элемента JSON."""
        if 'changed' in item:
            fields = item['changed'].get('fields', [])
            return f'Изменены поля: {", ".join(fields)}'
        if 'added' in item:
            return f'Добавлено: {item["added"].get("name", "объект")}'
        if 'deleted' in item:
            return f'Удалено: {item["deleted"].get("name", "объект")}'
        return ''

    def parsed_change_message(self, obj) -> str:
        """Парсит JSON-сообщение лога в читаемый вид."""
        if not obj.change_message:
            return ''
        try:
            data = json.loads(obj.change_message)
            # Приводим всё к списку (даже если это один словарь)
            items = data if isinstance(data, list) else [data]

            results = [self._format_item(item) for item in items]
            return ' | '.join(filter(None, results))
        except (json.JSONDecodeError, TypeError):
            return obj.change_message

    parsed_change_message.short_description = 'Изменения'

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
