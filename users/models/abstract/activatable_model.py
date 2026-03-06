from django.db import models


class ActivatableModel(models.Model):
    """Абстрактная модель с признаком активности."""
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        abstract = True
