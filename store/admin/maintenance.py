"""Админка сервисных операций."""

import datetime

from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone

from store.models import MaintenanceOperations
from store.tasks.maintenance import (
    create_missing_payouts,
    schedule_missing_album_archives,
    schedule_missing_reports,
    schedule_missing_track_audio,
)


@admin.register(MaintenanceOperations)
class MaintenanceOperationsAdmin(admin.ModelAdmin):
    """Запуск безопасных сервисных операций."""

    def changelist_view(self, request, extra_context=None):
        if request.method == 'POST':
            return self._handle_operation(request)

        previous_month_end = timezone.localdate().replace(
            day=1,
        ) - datetime.timedelta(days=1)

        context = {
            **self.admin_site.each_context(request),
            'title': 'Сервисные операции',
            'opts': self.model._meta,
            'previous_month': previous_month_end.strftime('%Y-%m'),
        }

        return TemplateResponse(
            request,
            'admin/store/maintenance_operations.html',
            context,
        )

    def _handle_operation(self, request) -> HttpResponse:
        """Ставит выбранную сервисную операцию в очередь."""
        operation = request.POST.get('operation')

        if operation == 'audio':
            schedule_missing_track_audio.delay()
            message = 'Проверка недостающего аудио поставлена в очередь.'

        elif operation == 'archives':
            schedule_missing_album_archives.delay()
            message = 'Проверка архивов поставлена в очередь.'

        elif operation == 'reports':
            month = request.POST.get('month')

            try:
                period_start = datetime.date.fromisoformat(
                    f'{month}-01',
                )
            except (TypeError, ValueError):
                self.message_user(
                    request,
                    'Некорректный отчетный месяц.',
                    level=messages.ERROR,
                )
                return redirect(request.path)

            next_month = (
                period_start.replace(day=28) + datetime.timedelta(days=4)
            ).replace(day=1)

            period_end = next_month - datetime.timedelta(days=1)

            schedule_missing_reports.delay(
                period_start.isoformat(),
                period_end.isoformat(),
            )
            message = (
                'Проверка отчетов за '
                f'{period_start:%m.%Y} поставлена в очередь.'
            )

        elif operation == 'payouts':
            create_missing_payouts.delay()
            message = 'Проверка выплат поставлена в очередь.'

        else:
            self.message_user(
                request,
                'Неизвестная сервисная операция.',
                level=messages.ERROR,
            )
            return redirect(request.path)

        self.message_user(
            request,
            message,
            level=messages.SUCCESS,
        )

        return redirect(request.path)

    def has_add_permission(self, request):
        return False

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
