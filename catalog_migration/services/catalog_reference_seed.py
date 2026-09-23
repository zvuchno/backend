"""Create-only starter references; never overwrite a manually edited row."""

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog_migration.services.catalog_reference_data import (
    GENRES,
    MERCH_KINDS,
)

from store.models import Genre, MerchKind


def ensure_reference(model, row, *, apply=False):
    """Validate or create one reference row without overwriting it."""
    current = (
        model.objects.select_for_update().filter(slug=row['slug']).first()
    )
    if current is not None:
        if any(getattr(current, k) != v for k, v in row.items()):
            raise ValidationError(
                f'{model.__name__}: existing slug {row["slug"]} differs; '
                'not overwritten',
            )
        return current, 'existing'
    candidate = model(**row)
    candidate.full_clean()
    if apply:
        candidate.save()
        return candidate, 'created'
    return candidate, 'would_create'


@transaction.atomic
def seed_references(*, apply=False):
    """Validate or create the migration's required reference rows."""
    result = {'created': 0, 'existing': 0, 'would_create': 0}
    for model, rows in [(MerchKind, MERCH_KINDS), (Genre, GENRES)]:
        for row in rows:
            _, status = ensure_reference(model, row, apply=apply)
            result[status] += 1
    return result
