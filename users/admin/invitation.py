from django.contrib import admin

from users.models import ArtistProfileClaimInvitation


@admin.register(ArtistProfileClaimInvitation)
class ArtistProfileClaimInvitationAdmin(admin.ModelAdmin):
    """Приглашения к управлению профилем артиста."""

    list_display = (
        'id',
        'artist',
        'label',
        'recipient_email',
        'status',
        'expires_at',
        'created_by',
        'responded_by',
        'created_at',
    )

    list_display_links = (
        'id',
        'artist',
        'recipient_email',
    )

    search_fields = (
        'artist__name',
        'artist__label__name',
        'invitation__recipient_email',
        'invitation__created_by__email',
        'invitation__responded_by__email',
    )

    list_filter = (
        'invitation__status',
        'invitation__created_at',
        'invitation__expires_at',
    )

    list_select_related = (
        'artist',
        'artist__label',
        'invitation',
        'invitation__created_by',
        'invitation__responded_by',
    )

    readonly_fields = (
        'invitation',
        'artist',
        'recipient_email',
        'status',
        'expires_at',
        'created_by',
        'responded_by',
        'responded_at',
        'created_at',
        'updated_at',
    )

    @admin.display(description='Лейбл')
    def label(self, obj):
        return obj.artist.label

    @admin.display(description='Email')
    def recipient_email(self, obj):
        return obj.invitation.recipient_email

    @admin.display(description='Статус')
    def status(self, obj):
        return obj.invitation.get_status_display()

    @admin.display(description='Действует до')
    def expires_at(self, obj):
        return obj.invitation.expires_at

    @admin.display(description='Создано пользователем')
    def created_by(self, obj):
        return obj.invitation.created_by

    @admin.display(description='Ответивший пользователь')
    def responded_by(self, obj):
        return obj.invitation.responded_by

    @admin.display(description='Дата ответа')
    def responded_at(self, obj):
        return obj.invitation.responded_at

    @admin.display(description='Создано')
    def created_at(self, obj):
        return obj.invitation.created_at

    @admin.display(description='Обновлено')
    def updated_at(self, obj):
        return obj.invitation.updated_at

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
