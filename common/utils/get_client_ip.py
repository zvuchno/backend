def get_client_ip(request) -> str:
    """Возвращает IP-адрес клиента с учётом прокси."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')

    if forwarded:
        return forwarded.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR')


def get_user_agent(request) -> str:
    """Возвращает user agent."""
    return request.META.get('HTTP_USER_AGENT', '')
