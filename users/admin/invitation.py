from django.contrib import admin

from users.models import ArtistProfileClaimInvitation, TokenInvitation


@admin.register(TokenInvitation)
class TokenInvitationAdmin(admin.ModelAdmin):
    """Email инвайты с токеном."""

    list_display = (
        'id',
        'recipient_email',
        'status',
        'created_by',
        'responded_by',
        'expires_at',
        'created_at',
    )
    list_filter = (
        'status',
        'created_at',
        'expires_at',
    )
    search_fields = (
        'recipient_email',
        'created_by__email',
        'responded_by__email',
    )
    readonly_fields = (
        'token_hash',
        'created_by',
        'responded_by',
        'responded_at',
        'created_at',
        'updated_at',
    )

    def has_add_permission(self, request):
        return False


@admin.register(ArtistProfileClaimInvitation)
class ArtistProfileClaimInvitationAdmin(admin.ModelAdmin):
    """Приглашения артистов к управлению профилем."""

    list_display = (
        'id',
        'artist',
        'recipient_email',
        'status',
        'created_at',
    )
    search_fields = (
        'artist__name',
        'invitation__recipient_email',
    )
    list_select_related = (
        'artist',
        'invitation',
    )

    @admin.display(description='Email')
    def recipient_email(self, obj):
        return obj.invitation.recipient_email

    @admin.display(description='Статус')
    def status(self, obj):
        return obj.invitation.get_status_display()

    @admin.display(description='Создано')
    def created_at(self, obj):
        return obj.invitation.created_at

    def has_add_permission(self, request):
        return False
