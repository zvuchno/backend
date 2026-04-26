from rest_framework.permissions import BasePermission


class IsUserVerified(BasePermission):
    """Требует подтверждённый аккаунт."""

    message = 'Требуется подтверждённый аккаунт.'

    def has_permission(self, request, view):
        user = request.user
        return (
            user
            and user.is_authenticated
            and (user.is_email_verified or user.is_phone_verified)
        )
