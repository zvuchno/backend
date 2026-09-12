"""Тесты админки юридического профиля."""

import pytest
from django.contrib import admin
from django.db.models import QuerySet
from django.test import RequestFactory

from users.admin.artist_legal_profile import (
    ArtistLegalProfileAdmin,
    VerificationReadinessFilter,
)
from users.models import ArtistLegalProfile

pytestmark = pytest.mark.django_db


def _filter_queryset(value, queryset) -> QuerySet:
    """Применяет фильтр готовности профиля."""
    request = RequestFactory().get(
        '/admin/users/artistlegalprofile/',
        {
            'verification_readiness': value,
        },
    )
    model_admin = ArtistLegalProfileAdmin(
        ArtistLegalProfile,
        admin.site,
    )
    list_filter = VerificationReadinessFilter(
        request,
        {
            'verification_readiness': [value],
        },
        ArtistLegalProfile,
        model_admin,
    )

    return list_filter.queryset(
        request,
        queryset,
    )


def test_readiness_filter_finds_encrypted_ready_profile(
    artist_user,
    artist_legal_profile_factory,
):
    """Фильтр считает заполненный encrypted-профиль готовым."""
    legal_profile = artist_legal_profile_factory(
        user=artist_user,
    )

    queryset = _filter_queryset(
        'yes',
        ArtistLegalProfile.objects.all(),
    )

    assert queryset.filter(pk=legal_profile.pk).exists()


def test_readiness_filter_excludes_incomplete_encrypted_profile(
    artist_user,
    artist_legal_profile_factory,
):
    """Фильтр исключает профиль с пустым обязательным полем."""
    legal_profile = artist_legal_profile_factory(
        user=artist_user,
    )
    legal_profile.bank_data.bik = ''
    legal_profile.bank_data.save()

    ready_queryset = _filter_queryset(
        'yes',
        ArtistLegalProfile.objects.all(),
    )
    not_ready_queryset = _filter_queryset(
        'no',
        ArtistLegalProfile.objects.all(),
    )

    assert not ready_queryset.filter(
        pk=legal_profile.pk,
    ).exists()
    assert not_ready_queryset.filter(
        pk=legal_profile.pk,
    ).exists()
