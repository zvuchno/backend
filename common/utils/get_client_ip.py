def get_client_ip(request) -> str | None:
    """Возвращает IP-адрес клиента с учётом прокси."""
    if request is None:
        return None

    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')

    if forwarded:
        return forwarded.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR')


def get_user_agent(request) -> str:
    """Возвращает user agent."""
    if request is None:
        return ''

    return request.META.get('HTTP_USER_AGENT', '')
