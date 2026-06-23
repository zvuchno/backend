from urllib.parse import urlencode, urljoin

from config import settings


def build_frontend_url(path: str, params: dict[str, str]) -> str:
    """Строит абсолютный URL фронтенда с query-параметрами."""
    url = urljoin(
        f'{settings.FRONTEND_BASE_URL.rstrip("/")}/',
        path.lstrip('/'),
    )
    return f'{url}?{urlencode(params)}'
