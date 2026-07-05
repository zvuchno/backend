from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet


class MerchImageInlineFormSet(BaseInlineFormSet):
    """Проверяет главное изображение в inline-форме мерча."""

    def clean(self):
        """Не допускает несколько главных изображений."""
        super().clean()

        if any(self.errors):
            return
        main_images_count = 0
        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue

            if form.cleaned_data.get('DELETE', False):
                continue

            if form.cleaned_data.get('is_main', False):
                main_images_count += 1

        if main_images_count > 1:
            raise ValidationError(
                'Можно выбрать только одно главное изображение.',
            )
