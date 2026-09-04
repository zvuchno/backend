from allauth.account.models import EmailAddress
from django.contrib import admin


@admin.register(EmailAddress)
class EmailAddressAdmin(admin.ModelAdmin):
    """Администрирование email-адресов allauth."""

    list_display = (
        'email',
        'user',
        'verified',
        'primary',
    )
    search_fields = (
        'email',
        'user__email',
        'user__username',
    )
    list_filter = (
        'verified',
        'primary',
    )
