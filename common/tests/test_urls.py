from common.utils.urls import build_frontend_url


def test_build_frontend_url_joins_base_path_and_params(settings):
    """Собирает абсолютный URL фронтенда с параметрами."""
    settings.FRONTEND_BASE_URL = 'https://dev.zvuchno.space/'

    url = build_frontend_url(
        '/verify/verify-success',
        {
            'uid': 'abc',
            'token': 'test-token',
        },
    )

    assert url == (
        'https://dev.zvuchno.space/verify/verify-success'
        '?uid=abc&token=test-token'
    )


def test_build_frontend_url_supports_root_path(settings):
    """Собирает ссылку на корневой маршрут фронтенда."""
    settings.FRONTEND_BASE_URL = 'https://dev.zvuchno.space'

    url = build_frontend_url('/', {'status': 'error'})

    assert url == 'https://dev.zvuchno.space/?status=error'
