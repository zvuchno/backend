"""Схемы OpenAPI для эндпоинтов учетной записи пользователя."""

from drf_spectacular.utils import extend_schema

me_schema = extend_schema(
    tags=['Account'],
    summary='Текущая учетная запись',
    description=(
        'Возвращает данные текущего авторизованного пользователя, '
        'включая контакты, флаги подтверждения и наличие активных профилей.'
    ),
)

change_phone_schema = extend_schema(
    tags=['Account'],
    summary='Изменить номер телефона',
    description=(
        'Обновляет номер телефона текущего пользователя. '
        'После изменения телефон помечается как неподтвержденный.'
    ),
)

change_password_schema = extend_schema(
    tags=['Account'],
    summary='Изменить пароль',
    description=('Изменяет пароль текущего пользователя по старому паролю.'),
)

password_reset_request_schema = extend_schema(
    tags=['Account'],
    auth=[],
    summary='Запросить восстановление пароля',
    description=(
        'Принимает email пользователя и инициирует процесс '
        'восстановления пароля. '
        'Если учетная запись существует, для нее формируется ссылка '
        'восстановления.'
    ),
)

password_reset_verify_schema = extend_schema(
    tags=['Account'],
    auth=[],
    summary='Проверить ссылку восстановления пароля',
    description=(
        'Проверяет корректность uid и токена из ссылки восстановления '
        'пароля и сообщает, действительна ли ссылка.'
    ),
)

password_reset_confirm_schema = extend_schema(
    tags=['Account'],
    auth=[],
    summary='Подтвердить восстановление пароля',
    description=(
        'Повторно проверяет uid и токен восстановления пароля, '
        'а затем устанавливает новый пароль пользователя.'
    ),
)

email_verification_schema = extend_schema(
    tags=['Account'],
    auth=[],
    summary='Подтвердить email',
    description='Подтверждает email пользователя по uid и токену.',
)

resend_verification_email_schema = extend_schema(
    tags=['Account'],
    summary='Повторно отправить письмо подтверждения',
    description=(
        'Повторно инициирует отправку ссылки для подтверждения email '
        'текущего пользователя.'
    ),
)

become_artist_schema = extend_schema(
    tags=['Account'],
    summary='Стать артистом',
    description=(
        'Создает профиль артиста для текущего авторизованного '
        'пользователя. '
        'Если профиль артиста уже существует, возвращает ошибку.'
    ),
)

change_username_schema = extend_schema(
    tags=['Account'],
    summary='Изменить имя пользователя (username)',
    description='Меняет имя пользователя, проверяет уникальность.',
)

set_password_schema = extend_schema(
    tags=['Account'],
    summary='Установить пароль',
    description=(
        'Устанавливает пароль текущему авторизованному пользователю, '
        'если у его учетной записи ещё нет пригодного для входа пароля. '
        'Например, после регистрации через социальную сеть.'
    ),
)
