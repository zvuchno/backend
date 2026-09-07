from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet


class MerchImageInlineFormSet(BaseInlineFormSet):
    """Проверяет главное изображение в inline-форме мерча."""

    def clean(self):
        """Не допускает несколько главных изображений."""
        super().clean()

        if any(self.errors):
            return

        main_images_count = sum(
            1
            for form in self.forms
            if not form.cleaned_data.get('DELETE', False)
            and form.cleaned_data.get('is_main', False)
        )

        if main_images_count > 1:
            raise ValidationError(
                'Можно выбрать только одно главное изображение.',
            )
