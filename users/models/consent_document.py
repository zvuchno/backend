"""Модуль модели юридических документов."""

import hashlib

from django.core.exceptions import ValidationError
from django.db import models

from users.models.abstract import ActivatableModel, TimestampModel


class ConsentDocument(ActivatableModel, TimestampModel):
    """Модель для хранения версионных юридических документов (ПДн, оферты..).

    Модель реализует принцип неизменяемости для юридически значимых данных.
    После создания записи, попытки изменения `content`, `document_type`
    или `version` будут пресекаться на этапе валидации (`clean`).

    Основные характеристики:
    - Неизменяемость: Запрещено редактировать существующие записи
    (кроме поля `is_active`).
    - Контроль целостности: При создании вычисляется SHA256-хеш контента,
    который затем используется для проверки неизменности текста.
    - Управление активностью: Гарантируется наличие не более одного активного
      документа (`is_active=True`) для каждого типа.
    - Валидация: Все ограничения проверяются при сохранении
    (`full_clean` внутри `save`), что защищает от невалидных состояний
    даже при обходе форм.
    """

    document_type = models.ForeignKey(
        'users.DocumentType',
        on_delete=models.CASCADE,
        verbose_name='Тип документа',
    )

    version = models.CharField('Версия', max_length=20)

    content = models.TextField('Содержание')  # Текст документа
    content_hash = models.CharField(  # SHA256
        'hash документа',
        max_length=64,
        blank=True,
    )

    def _calculate_hash(self) -> str:
        return hashlib.sha256(self.content.encode('utf-8')).hexdigest()

    def _set_hash(self) -> None:
        if self.content:
            new_hash = self._calculate_hash()
            self.content_hash = new_hash

    def clean(self) -> None:
        """Валидация документа."""
        super().clean()
        if self.pk:
            self._validate_immutability()
        else:
            self._validate_unique_version()
        if self.is_active:
            self._validate_single_active_version()

    def _validate_immutability(self) -> None:
        """Проверяет, что критические поля не изменились."""
        try:
            original = ConsentDocument.objects.only(
                'content_hash',
                'document_type',
                'version',
            ).get(pk=self.pk)
        except ConsentDocument.DoesNotExist:
            return

        errors = {}
        if original.content_hash != self._calculate_hash():
            errors['content'] = (
                'Текст документа изменять нельзя. Создайте новую версию.'
            )

        if original.document_type_id != self.document_type_id:
            errors['document_type'] = (
                'Нельзя менять тип уже созданного документа.'
            )

        if original.version != self.version:
            errors['version'] = (
                'Нельзя менять номер версии у существующего документа.'
            )

        if errors:
            raise ValidationError(errors)

    def _validate_unique_version(self) -> None:
        """Проверяет уникальность версии для нового документа."""
        if ConsentDocument.objects.filter(
            document_type=self.document_type,
            version=self.version,
        ).exists():
            raise ValidationError({
                'version': f'Документ типа "{self.document_type.name}" '
                f'с версией {self.version} уже существует.',
            })

    def _validate_single_active_version(self) -> None:
        """Проверяет: для данного типа существует только один активный."""
        active_qs = ConsentDocument.objects.filter(
            document_type=self.document_type,
            is_active=True,
        )
        if self.pk:
            active_qs = active_qs.exclude(pk=self.pk)

        if active_qs.exists():
            raise ValidationError({
                'is_active': (
                    f'Уже существует активный документ для типа '
                    f'"{self.document_type.name}". '
                    'Сначала деактивируйте старый документ.'
                ),
            })

    def save(self, *args, **kwargs):
        if not self.pk:
            self._set_hash()
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'юридический документ'
        verbose_name_plural = 'юридические документы'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('document_type',),
                condition=models.Q(is_active=True),
                name='unique_active_document_per_type',
                violation_error_message=(
                    'Уже существует активный документ такого типа. '
                    'Сначала деактивируйте старый документ.'
                ),
            ),
            models.UniqueConstraint(
                fields=('document_type', 'version'),
                name='unique_document_version',
            ),
        ]

    def __str__(self):
        return f'{self.document_type.name} (v{self.version})'
