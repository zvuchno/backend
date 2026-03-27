"""Схемы OpenAPI для эндпоинтов учетной записи пользователя."""

from drf_spectacular.utils import extend_schema

me_schema = extend_schema(
    tags=['Аккаунт'],
    summary='Текущая учетная запись',
    description=(
        'Возвращает данные текущего авторизованного пользователя, '
        'включая контакты, флаги подтверждения и наличие активных профилей.'
    ),
)

change_phone_schema = extend_schema(
    tags=['Аккаунт'],
    summary='Изменить номер телефона',
    description=(
        'Обновляет номер телефона текущего пользователя. '
        'После изменения телефон помечается как неподтвержденный.'
    ),
)

change_password_schema = extend_schema(
    tags=['Аккаунт'],
    summary='Изменить пароль',
    description=('Изменяет пароль текущего пользователя по старому паролю.'),
)

email_verification_schema = extend_schema(
    tags=['Аккаунт'],
    auth=[],
    summary='Подтвердить email',
    description='Подтверждает email пользователя по uid и токену.',
)

resend_verification_email_schema = extend_schema(
    tags=['Аккаунт'],
    summary='Повторно отправить письмо подтверждения',
    description=(
        'Повторно инициирует отправку ссылки для подтверждения email '
        'текущего пользователя.'
    ),
)
