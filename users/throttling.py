from rest_framework.throttling import SimpleRateThrottle


class RegistrationThrottle(SimpleRateThrottle):
    """Ограничивает регистрацию по IP-адресу."""

    scope = 'registration'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident,
        }
