"""URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/

Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))

"""

from allauth.socialaccount import providers
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

# Маршруты для документации API (OpenAPI 3.0)
docs_urlpatterns = [
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'swagger/',
        SpectacularSwaggerView.as_view(url_name='api-docs:schema'),
        name='swagger-ui',
    ),
    path(
        'redoc/',
        SpectacularRedocView.as_view(url_name='api-docs:schema'),
        name='redoc',
    ),
]


# Список эндпоинтов бизнес-логики (Store, Users и т.д.)
api_v1_urlpatterns = [
    path('store/', include('store.urls', namespace='store')),
    path('', include('users.urls', namespace='users')),
]


def redirect_social_auth_to_frontend(request):
    """Редирект на указанную страницу фронта."""
    target_url = getattr(settings, 'FRONTEND_SOCIAL_AUTH_URL', '/')
    return redirect(f'{target_url}?status=cancelled')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/docs/', include((docs_urlpatterns, 'api-docs'))),
    path('api/v1/', include((api_v1_urlpatterns, 'api'))),
    *[
        path(
            f'accounts/{provider.id}/',
            include(f'allauth.socialaccount.providers.{provider.id}.urls'),
        )
        for provider in providers.registry.get_class_list()
    ],
    path(
        'accounts/social/login/cancelled/',
        redirect_social_auth_to_frontend,
        name='socialaccount_login_cancelled',
    ),
    path(
        'accounts/social/login/error/',
        redirect_social_auth_to_frontend,
        name='socialaccount_login_error',
    ),
    path(
        'accounts/social/signup/',
        redirect_social_auth_to_frontend,
        name='socialaccount_signup',
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
