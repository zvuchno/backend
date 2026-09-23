"""Tests for the production reference preparation command."""

import pytest
from django.core.exceptions import ValidationError

from catalog_migration.services.catalog_reference_seed import seed_references

from store.models import Genre, MerchKind


@pytest.mark.django_db
def test_reference_seed_preview_repeat_and_manual_conflict():
    """Seed references create-only and preserve manual conflicts."""
    assert seed_references()['would_create'] == 22
    assert not Genre.objects.exists() and not MerchKind.objects.exists()
    assert seed_references(apply=True)['created'] == 22
    assert seed_references(apply=True)['existing'] == 22
    assert Genre.objects.count() == 13 and MerchKind.objects.count() == 9
    record = Genre.objects.get(slug='pop')
    record.name = 'Ручное название'
    record.save()
    with pytest.raises(ValidationError):
        seed_references(apply=True)
    record.refresh_from_db()
    assert record.name == 'Ручное название'
