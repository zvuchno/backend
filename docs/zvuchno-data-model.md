# Модель данных «Звучно»: текущая реализация

## Назначение и границы документа

Этот документ — справочник по **существующей** реализации Django-приложений `users` и `store`. Он предназначен для ИИ, который помогает проектировать прототипы интерфейсов: какие объекты существуют, какие поля и состояния можно показывать пользователю, какие действия реально поддерживает backend.

Документ не является новым ТЗ и не описывает желаемую архитектуру. В нём нет реальных данных БД, значений переменных окружения и инфраструктурных секретов. Выводы сделаны по моделям, сериализаторам, сервисам, проверкам доступа, публикации и фоновым задачам репозитория.

Обозначения:

- **Подтверждено** — поведение явно задано моделью, ограничением БД, сериализатором, сервисом или проверкой доступа.
- **Зависит от настройки** — ветка существует в коде, но фактическое значение runtime-настройки в этом документе не определяется.
- **Не определено** — код содержит состояние или поле, но допустимый пользовательский переход либо его смысл полностью не зафиксирован.
- `null=True` означает, что БД допускает `NULL`; `blank=True` — что Django-валидация допускает пустое значение. Для строк с `blank=True, default=''` типичное пустое значение — пустая строка, не `NULL`.
- Большинство контентных и профильных моделей наследуют `created_at`, `updated_at`; многие также наследуют `is_active=True`. Источники: `common/models/abstract/timestamp_model.py`, `common/models/abstract/activatable_model.py`.

## 1. Карта основных сущностей

### 1.1. Пользователи и профили

| Сущность | Назначение | Ключевые связи |
|---|---|---|
| `CoreUser` | Учётная запись и данные входа | 0..1 профиль слушателя, 0..1 профиль артиста/лейбла, 0..1 юридический профиль |
| `ListenerProfile` | Роль и пользовательские данные слушателя | ровно один `CoreUser` |
| `ArtistProfile` | Публичный профиль артиста или лейбла | 0..1 владелец `CoreUser`; артист может принадлежать 0..1 лейблу |
| `ArtistLegalProfile` | Юридический статус получателя выплат | ровно один `CoreUser`; по одному блоку банковских, физических или корпоративных данных |
| `ArtistContact`, `ArtistSocial` | Публичные контакты и ссылки артиста | много записей на один `ArtistProfile` |
| `ArtistStoreSettings` | Включение доставки и самовывоза | 0..1 набор настроек на профиль |
| `ArtistShippingPoint` | ПВЗ отправителя для СДЭК | 0..1 точка на профиль |
| `ArtistPickupPoint` | Точка самовывоза покупателем | много точек на профиль |
| `TokenInvitation` | Универсальное токен-приглашение | создатель и, опционально, ответивший пользователь |
| `ArtistProfileClaimInvitation` | Приглашение принять управление профилем артиста | ровно одно приглашение и ровно один профиль артиста |
| `ConsentDocument` | Версия юридического документа | много фактов согласия `UserConsent` |
| `UserConsent` | Факт принятия конкретной версии документа | пользователь и/или email; опционально заказ и артист |
| `EmailVerificationCode` | Текущий код подтверждения email | 0..1 код на пользователя |

Источники: `users/models/core_user.py`, `users/models/listener_profile.py`, `users/models/artist/*.py`, `users/models/invitation.py`, `users/models/consents/*.py`, `users/models/email_verification_code.py`.

### 1.2. Каталог, файлы и коммерция

| Сущность | Назначение | Ключевые связи |
|---|---|---|
| `Genre` | Справочник музыкальных жанров | один жанр может быть у многих релизов |
| `Album` | Релиз: альбом или сингл | один артист, 0..1 жанр, много треков, 0..1 товар |
| `Track` | Трек внутри конкретного релиза | ровно один альбом, 0..1 товар, загрузки и производное аудио |
| `AlbumArchive` | ZIP оригиналов опубликованного релиза | 0..1 архив на альбом |
| `TrackUpload` | Попытка прямой загрузки или замены оригинала | много попыток на трек |
| `TrackGeneratedAudio` | Preview и stream, созданные из оригинала | 0..1 запись на трек |
| `MerchKind` | Справочник типов мерча | один тип у многих единиц мерча |
| `Merch` | Физический товар/носитель | один артист; 0..1 связанный релиз; 0..1 товар |
| `Image` | Изображение мерча | много изображений на единицу мерча |
| `Product` | Коммерческая обвязка одного альбома, трека или мерча | ровно одна из трёх связей; много SKU |
| `ProductVariant` | Покупаемый SKU | ровно один `Product`; остаток и значение свойства |

Источники: `store/models/genre.py`, `store/models/album.py`, `store/models/track.py`, `store/models/merch_kind.py`, `store/models/merch.py`, `store/models/image.py`, `store/models/product.py`, `store/models/product_variant.py`.

### 1.3. Покупка, доставка и расчёты

| Сущность | Назначение | Ключевые связи |
|---|---|---|
| `Cart` | Корзина аккаунта или анонимной сессии | 0..1 пользователь; много позиций; 0..1 промокод |
| `CartItem` | Выбранный SKU, количество, доплата и комментарий | один `Cart`, один `ProductVariant` |
| `Favorite` | Избранный SKU пользователя | один пользователь и один вариант |
| `Promocode` | Скидка на товары конкретного артиста | один артист; много корзин и заказов |
| `Delivery` | Справочник способов доставки | много заказов |
| `Order` | Зафиксированный заказ | 0..1 пользователь; много позиций, платежей и отправлений |
| `OrderItem` | Снимок проданного SKU и финансовых данных | один заказ, один защищённый от удаления SKU, артист и получатель выплат |
| `Payment` | Попытка оплаты заказа | много платежей на заказ |
| `Shipment` | Отправление СДЭК от одного артиста | уникальная пара заказ + артист |
| `Report` | Агрегированный отчёт получателя выплат за период | один получатель; 0..1 выплата |
| `Payout` | Ручная выплата по готовому отчёту | ровно один отчёт и один получатель |

Источники: `store/models/cart.py`, `store/models/cart_item.py`, `store/models/favorite.py`, `store/models/promocode.py`, `store/models/delivery.py`, `store/models/order.py`, `store/models/order_item.py`, `store/models/payment.py`, `store/models/shipment.py`, `store/models/report.py`, `store/models/payout.py`.

### 1.4. Read-only представления

| Сущность | Назначение | Идентичность |
|---|---|---|
| `ListenerTrackAccess` | Факт доступа пользователя к треку после покупки | составной ключ `(user, track)` |
| `ListenerAlbumAccess` | Доступ к релизу и признак доступа ко всем его трекам | составной ключ `(user, album)` |
| `CatalogSearch` | Материализованный поисковый индекс альбомов, треков, мерча и артистов | логическая идентичность `(entity_type, entity_id)`; поле `id` нестабильно после refresh |

Эти модели имеют `managed=False`: ORM их читает, но не управляет таблицами/представлениями. Источники: `store/models/music_access.py`, `store/models/catalog_search.py`, `store/migrations/sql/views/*.sql`.

Ещё две технические модели не являются самостоятельными пользовательскими сущностями:

- `OrderNumberCounter` хранит уникальный год и последний номер для атомарной нумерации заказов;
- `MaintenanceOperations` — proxy-модель над `Album` без собственной таблицы, используемая только как точка входа в сервисный раздел admin для суперпользователя.

Источники: `store/models/order.py: OrderNumberCounter`, `store/models/maintenance.py`, `store/admin/maintenance.py`.

## 2. Связи и кардинальность

### 2.1. Пользовательские связи

- `CoreUser 1 — 0..1 ListenerProfile`: `OneToOne`, профиль удаляется вместе с пользователем (`CASCADE`). Источник: `users/models/listener_profile.py`.
- `CoreUser 1 — 0..1 ArtistProfile`: `OneToOne`, связь профиля может быть пустой; удаление пользователя защищено `PROTECT`, если он владеет профилем. Профиль, созданный лейблом, может не иметь аккаунта. Источник: `users/models/artist/profile.py`.
- `ArtistProfile(label) 1 — 0..N ArtistProfile(artist)`: самоссылка `label`; допустима только для профиля типа `artist`, родитель должен иметь тип `label`. Источник: `users/models/artist/profile.py: ArtistProfile.clean` и DB constraints.
- `CoreUser 1 — 0..1 ArtistLegalProfile`; юридический профиль удаляется вместе с пользователем. Источник: `users/models/artist/legal_profile.py`.
- `ArtistLegalProfile 1 — 0..1 ArtistIdentityData / ArtistBankData / ArtistCompanyData`: отдельные `OneToOne`-блоки. Источники: `users/models/artist/identity_data.py`, `bank_data.py`, `company_data.py`.
- `ArtistProfile 1 — 0..N ArtistContact / ArtistSocial / ArtistPickupPoint`; `ArtistProfile 1 — 0..1 ArtistShippingPoint / ArtistStoreSettings`. Источники: соответствующие файлы в `users/models/artist/`.
- `ArtistProfile 1 — 0..1 ArtistProfileClaimInvitation` и `TokenInvitation 1 — 0..1 ArtistProfileClaimInvitation`: повторное независимое приглашение для того же профиля создать нельзя, пока существует связующая запись. Источники: `users/models/invitation.py`, `users/services/invitation.py: _validate_claim_not_exists`.
- `ConsentDocument 1 — 0..N UserConsent`; удаление принятого документа запрещено (`PROTECT`). `UserConsent` может пережить удаление пользователя, заказа или артиста: эти ссылки становятся `NULL`. Источник: `users/models/consents/user_consent.py`.

### 2.2. Контент и коммерция

- `ArtistProfile 1 — 0..N Album` и `ArtistProfile 1 — 0..N Merch`; удаление артиста защищено (`PROTECT`). Автор создания и получатель выплат — отдельные ссылки на `CoreUser`, обе могут быть `NULL` у черновика. Источник: `store/models/abstract/base_content.py`.
- `Album 1 — 0..N Track`; удаление альбома каскадно удаляет треки. В текущей модели один `Track` не может принадлежать нескольким релизам. Источник: `store/models/track.py`.
- `Album 1 — 0..N Merch`; связь необязательна, удаление альбома каскадно удаляет связанный мерч. Источник: `store/models/merch.py`.
- `Album 1 — 0..1 AlbumArchive`, `Track 1 — 0..1 TrackGeneratedAudio`, `Track 1 — 0..N TrackUpload`: все дочерние объекты каскадно удаляются вместе с контентом. Источники: `store/models/album.py`, `store/models/track.py`.
- `Merch 1 — 0..N Image`; БД допускает не более одного изображения с `is_main=True` на мерч. Источник: `store/models/image.py`.
- `Product 1 — ровно 1 Album/Track/Merch`: технически это три nullable `OneToOne`, но DB check требует заполнить ровно одну ссылку, совпадающую с `product_type`. Поэтому у контентного объекта бывает не более одного `Product`. Источник: `store/models/product.py: Product.determine_product_type, Meta.constraints`.
- `Product 1 — 1..N ProductVariant` в штатном API: сервис гарантирует цифровой вариант альбомам и трекам и вариант(ы) мерчу. Сама БД допускает продукт без вариантов. Источник: `store/services/commerce.py: ProductService.ensure_commerce`.

### 2.3. Продажи

- `CoreUser 1 — 0..1 Cart`, но корзина может вместо пользователя иметь `session_key`. DB check требует хотя бы одного владельца; одновременно заполненные `user` и `session_key` не запрещены. Источник: `store/models/cart.py`.
- `Cart 1 — 0..N CartItem`; пара `(cart, product_variant)` уникальна. Источник: `store/models/cart_item.py`.
- `CoreUser N — M ProductVariant` через `Favorite`; пара уникальна. Источник: `store/models/favorite.py`.
- `Order 1 — 1..N OrderItem` в штатном checkout; БД допускает пустой заказ. Пара `(order, product_variant)` уникальна. Источники: `store/models/order_item.py`, `store/services/order_service.py`.
- `Order 1 — 0..N Payment`; сервис переиспользует существующий `pending`-платёж, но DB не ограничивает число pending-платежей. Источник: `store/services/payment.py: create_yookassa_payment`.
- `Order 1 — 0..N Shipment`; на одного артиста в заказе не более одного отправления. Источник: `store/models/shipment.py`.
- `Report 1 — 0..1 Payout`; удаление отчёта или получателя выплаты после появления выплаты защищено. Источник: `store/models/payout.py`.

## 3. Поля, перечисления и ограничения

### 3.1. `users`: аккаунты и роли

#### `CoreUser`

- Наследует стандартного Django-пользователя: `username`, пароль, staff/superuser, active и прочие стандартные поля.
- `email`: обязательный для модели входа, `unique=True`; нормализуется перед сохранением.
- `phone`: `unique=True`, `null=True`, `blank=True`.
- `is_email_verified`, `is_phone_verified`: boolean, по умолчанию `False`.
- Вход настроен по email (`USERNAME_FIELD = 'email'`), а `username` остаётся обязательным полем.

Источник: `users/models/core_user.py`.

#### `ListenerProfile`

- `user`: обязательный уникальный `OneToOne`.
- `full_name`: `blank=True`, по умолчанию `''`.
- `is_active`: по умолчанию `True`.

Источник: `users/models/listener_profile.py`.

#### `ArtistProfile`

- `profile_type`: `artist` или `label`, по умолчанию `artist`.
- `user`: `OneToOne`, `null=True`, `blank=True`.
- `label`: ссылка на другой `ArtistProfile`, `null=True`, `blank=True`, ограничена профилями типа `label`.
- `name`: обязательное название с валидаторами длины.
- `slug`: уникальный; может быть не передан, тогда формируется автоматически с уникальным суффиксом. В API обновления пустая строка запрещена.
- `city`, `description`: допускают пустую строку; имеют валидаторы длины.
- `cover`: `null=True`, `blank=True`.
- `telegram_chat_id`, `telegram_connect_token`: уникальны, `null=True`, `blank=True`.
- `is_active`: по умолчанию `True`.
- DB constraints: лейбл не может иметь родительский лейбл; профиль не может ссылаться на себя как на лейбл.

Источники: `users/models/artist/profile.py`, `users/serializers/artist_profile.py`.

#### Юридический профиль

`ArtistLegalProfile`:

- `user`: обязательный `OneToOne`.
- `email`: `blank=True`, по умолчанию `''`; `phone`: `null=True`, `blank=True`.
- `recipient_type`: `''` (не выбран), `individual_entrepreneur`, `self_employed`, `legal_entity`; поле допускает пустое значение.
- `is_verified=False`; `comment` пустой по умолчанию и доступен только для чтения через пользовательский API.

`ArtistBankData` содержит `bank_name`, `bik`, `correspondent_account`, `checking_account`; все допускают пустую строку. Часть значений хранится зашифрованно на уровне полей.

`ArtistIdentityData` содержит ФИО, дату рождения, адрес регистрации, паспортные данные и ИНН; строки допускают пустое значение, даты — `null=True, blank=True`. Чувствительные поля зашифрованы.

`ArtistCompanyData` содержит `company_name`, `company_address`, `inn`, `ogrn`; поля допускают пустую строку.

Источники: `users/models/artist/legal_profile.py`, `bank_data.py`, `identity_data.py`, `company_data.py`; состав пользовательского payload — `users/serializers/artist_legal_profile.py`.

#### Контакты и доставка артиста

- `ArtistContact`: обязательные `artist`, `label`, `value` (email); уникальности нет.
- `ArtistSocial`: обязательные `artist`, `label`, `value` (URL); уникальности нет.
- `ArtistStoreSettings`: уникальный профиль; `shipping_enabled=False`, `pickup_enabled=False`.
- `ArtistShippingPoint`: уникальный профиль; обязательные `pvz_code`, `city_code`, `city`, `address`.
- `ArtistPickupPoint`: обязательные `artist`, `address`; `pickup_date` — `null=True, blank=True`; активные точки уникальны по `(artist, address, pickup_date)`, причём `NULL` в дате считается равным благодаря `nulls_distinct=False`.

Источники: `users/models/artist/contact.py`, `social.py`, `store_settings.py`, `shipping_point.py`, `pickup_point.py`.

### 3.2. `users`: приглашения и согласия

#### `TokenInvitation` и `ArtistProfileClaimInvitation`

- Статусы: `pending`, `accepted`, `rejected`, `revoked`, `expired`.
- `recipient_email`, `expires_at`, `created_by` обязательны.
- Хранится уникальный `token_hash`, не исходный токен.
- `send_count=0`; `last_sent_at`, `responded_by`, `responded_at` допускают `NULL`.
- `ArtistProfileClaimInvitation` использует две `OneToOne`-связи: одно приглашение относится не более чем к одному claim, а профиль имеет не более одного claim.

Источник: `users/models/invitation.py`.

#### `ConsentDocument`

Типы документов:

- `privacy_policy`;
- `artist_offer`, `artist_personal_data`, `artist_distribution`, `artist_newsletter`;
- `listener_offer`, `listener_personal_data`, `listener_distribution`, `listener_newsletter`.

Ключевые ограничения:

- уникальна пара `(document_type, version)`;
- для каждого типа не более одной активной версии;
- после создания нельзя менять тип, версию и содержание; `content_hash` фиксирует SHA-256 текста;
- фактически изменяемым бизнес-полем существующего документа остаётся `is_active`.

Источник: `users/models/consents/consent_document.py`.

#### `UserConsent`

- Обязательны `email` и `document`.
- `user`, `order`, `artist`, `ip_address`, `user_agent`, `revoked_at` — nullable/blank.
- `accepted_at` устанавливается автоматически.
- Уникального ограничения на повторное принятие того же документа нет.

Источник: `users/models/consents/user_consent.py`.

### 3.3. `store`: каталог и публикация

#### Общие поля контента

`BaseContent`: обязательное `name`; `description` допускает пустую строку; `created_by` — `null=True, blank=True`, `PROTECT`; `is_active=True`.

`ArtistContent` добавляет обязательного `artist` и nullable `payout_recipient` (`CoreUser`, `PROTECT`).

`VisibilityModel` добавляет:

- `visibility`: `public`, `link_only`, `hidden`; по умолчанию `public`;
- `is_published=False`.

Источники: `store/models/abstract/base_content.py`, `store/models/abstract/visibility_model.py`.

#### `Genre`

- `name` и `slug` уникальны; `is_active=True`.

Источник: `store/models/genre.py`.

#### `Album`

- `release_date`: `null=True`, `blank=True`.
- `genre`: `SET_NULL`, `null=True`, `blank=True`.
- `is_single=False`.
- `cover_image`: публичное хранилище, `null=True`, `blank=True`.
- DB check: опубликованный альбом обязан иметь `payout_recipient`.

Источник: `store/models/album.py`.

#### `Track`

- `album`: обязательный FK; артист и получатель выплат вычисляются через альбом.
- `audio_file`: приватное хранилище, `blank=True`, но не `null=True`; разрешены MP3/WAV/FLAC и ограничен размер.
- `duration`: секунды, `null=True`, `blank=True`.
- `position`: положительное число, `null=True`, `blank=True`.
- Уникальности позиции внутри альбома нет.
- У трека нет собственных `visibility` и `is_published`; они наследуются логикой выборки от альбома.

Источник: `store/models/track.py`, `store/querysets/track_visibility.py`.

#### Файловые сущности трека и релиза

- `TrackUpload.status`: `initiated`, `uploaded`, `completed`, `failed`, `expired`.
- `TrackUpload.purpose`: `create`, `replace`.
- `staging_key` уникален; размер, имя и срок обязательны; фактический размер и `completed_at` nullable.
- `TrackGeneratedAudio` отдельно хранит preview и stream. Для каждого используются состояния `pending`, `building`, `ready`, `failed`, собственные файл, ошибка и время старта; длительность preview nullable.
- `AlbumArchive.status`: `pending`, `building`, `ready`, `failed`; файл может быть пустым; `content_hash` описывает состав исходных данных, а не байты ZIP.

Источники: `store/models/track.py`, `store/models/album.py`.

#### `MerchKind`, `Merch`, `Image`

- `MerchKind`: `name` не уникально; `slug` уникален; `is_carrier=False`; `is_active=True`.
- `Merch.kind`: `null=True`, но без `blank=True`; в формах поле считается обязательным, хотя БД допускает `NULL`.
- `Merch.album`: `null=True`, `blank=True`; используется для привязки носителя к релизу.
- DB check: опубликованный мерч обязан иметь `payout_recipient`.
- `Image.image` обязателен; `is_main=False`; не более одного `is_main=True` на мерч независимо от `is_active` изображения.

Источники: `store/models/merch_kind.py`, `store/models/merch.py`, `store/models/image.py`.

### 3.4. `store`: товары, корзина и заказ

#### `Product`

- `product_type`: `track`, `album`, `merch`.
- `price`: неотрицательное decimal, по умолчанию 0.
- `allow_overpay=False`.
- `property_name`: пустая строка по умолчанию.
- Ровно одна nullable `OneToOne`-ссылка из `album`, `track`, `merch`; тип обязан ей соответствовать.

Источник: `store/models/product.py`.

#### `ProductVariant`

- `product`: обязательный FK.
- `sku`: глобально уникален, может быть пустым до автогенерации при первом сохранении.
- `stock`: `null=True`, `blank=True`, по умолчанию 0. `NULL` означает цифровой вариант без складского учёта.
- `property_value`: пустая строка по умолчанию.
- Уникальна пара `(product, property_value)`.
- `is_active=True`.

Источник: `store/models/product_variant.py`.

#### `Cart` и `CartItem`

- У пользователя не более одной корзины; непустой `session_key` также уникален.
- Корзина обязана иметь пользователя или сессию; `promocode` необязателен и обнуляется при удалении промокода.
- В позиции обязательны вариант и `quantity>=1`; `price_with_donation`, `comment` nullable/blank; `is_artist_subscription=False`.
- Цифровой вариант допускается в количестве не более 1 на уровне модельной валидации и API.

Источники: `store/models/cart.py`, `store/models/cart_item.py`, `store/serializers/cart.py`.

#### `Promocode`

- Тип скидки: `PERCENT` или `FIXED`.
- `code` глобально уникален и проходит форматные валидаторы.
- `discount_value>=0.01`; для процента — не более 100.
- `usage_limit`, `start_at`, `end_at` nullable; `used_count=0`.
- Действие одновременно контролируют `is_active` и `is_enabled`; период при двух датах должен иметь `end_at > start_at`.

Источник: `store/models/promocode.py`.

#### `Delivery`, `Order`, `OrderItem`

`Delivery.delivery_type`: `courier`, `pickpoint`, `artist_pickup`; способ может быть деактивирован через `is_active`.

`Order.status`: `created`, `reserved`, `paid`, `shipped`, `completed`, `canceled`.

- `user`: `null=True`, `blank=True`, `SET_NULL`, хотя текущий endpoint checkout требует аутентификацию.
- `order_number`: уникален, создаётся в формате с годом и атомарным годовым счётчиком.
- `full_name`, `email`, `phone` обязательны.
- `delivery` nullable/blank и защищена от удаления; адресные поля допускают пустую строку.
- `pickup_point` и `delivery_calculation` — JSON-снимки, а не живые FK.
- `promocode`: nullable, `SET_NULL`.
- суммы неотрицательны; `reserved_until` nullable.

`OrderItem`:

- `product_variant` — `PROTECT`; товар нельзя удалить после появления позиции заказа через эту связь;
- `artist` и `payout_recipient` — обязательные `PROTECT`-ссылки;
- `product_info` хранит JSON-снимок названия, типа, артиста, свойства, SKU, `allow_overpay` и кода промокода;
- `quantity>=1`; уникальна пара `(order, product_variant)`;
- DB checks: `unit_price >= price_at_purchase`; скидка не превышает `unit_price * quantity`.

Источники: `store/models/delivery.py`, `store/models/order.py`, `store/models/order_item.py`, `store/services/order_service.py: _create_order_items`.

#### `Payment`, `Shipment`, `Report`, `Payout`

- `Payment.status`: `pending`, `succeeded`, `canceled`, `failed`. `provider_payment_id` уникален, но nullable; `paid_at` и `error_code` nullable; `idempotency_key` уникален.
- `Shipment.state`: `CREATED`, `ACCEPTED`, `WAITING`, `SUCCESSFUL`, `INVALID`; `cdek_uuid` и номер накладной допускают пустую строку; вес nullable; уникальна пара `(order, artist)`.
- `Report.status`: `pending`, `ready`, `failed`; файл nullable/blank; уникален период `(payout_recipient, period_start, period_end)`.
- `Payout.status`: `pending`, `on_hold`, `paid`; одна выплата на отчёт; `paid_at` nullable, комментарий blank.

Источники: `store/models/payment.py`, `store/models/shipment.py`, `store/models/report.py`, `store/models/payout.py`.

## 4. Бизнес-правила за пределами структуры БД

### 4.1. Создание ролей и управление артистами

**Подтверждено:** регистрация слушателя создаёт `CoreUser + ListenerProfile`; регистрация артиста или лейбла создаёт `CoreUser + ListenerProfile + ArtistProfile`. Один аккаунт тем самым может одновременно быть слушателем и артистом/лейблом. Источники: `users/serializers/listener_registration.py`, `users/serializers/artist_registration.py`.

**Подтверждено:** аккаунт без `ArtistProfile` может создать профиль `artist` или `label`. Независимый активный артист может повыситься только до `label`; обратный переход не реализован. Артист, уже прикреплённый к лейблу, стать лейблом не может. Источник: `users/serializers/artist_profile.py: BecomeArtistOrLabelSerializer`.

**Подтверждено:** лейбл может создать управляемый профиль артиста без аккаунта. Такой профиль получает `profile_type=artist`, `label=<текущий лейбл>`, `user=NULL`. Источник: `users/serializers/artist_profile.py: ManagedArtistProfileCreateSerializer`.

**Подтверждено:** управлять профилем может его собственный пользователь либо пользователь родительского лейбла. Для API управляемых профилей дополнительно требуется активность профиля. Источники: `common/access/artists.py`, `users/views/mixins/managed_profiles.py`.

**Подтверждено:** удалить через API созданный лейблом профиль можно лишь пока у него нет аккаунта, альбомов и мерча. Источник: `users/views/artist_profile.py: ManagedArtistProfileView.delete`.

**Подтверждено:** при присоединении/отсоединении от лейбла `payout_recipient` всех существующих альбомов и мерча синхронизируется: это пользователь лейбла либо собственный пользователь артиста. Нельзя оставить опубликованный контент без получателя выплат. Для самостоятельного выхода требуются аккаунт артиста, подтверждённый email и верифицированный юридический профиль. Источник: `users/services/artist_membership.py`.

### 4.2. Юридические данные и согласия

**Подтверждено:** обязательность юридических блоков зависит от `recipient_type`:

- банковские `bik` и `checking_account` всегда входят в проверку готовности; отдельно обязательно выбрать `recipient_type`;
- ФИО, дата рождения, адрес регистрации, паспорт и личный ИНН — для самозанятого и ИП;
- название, адрес, ИНН и ОГРН организации — для юрлица.

Источник: `users/models/artist/legal_profile.py: get_verification_missing_fields`.

**Подтверждено:** любое фактическое изменение юридического профиля или связанных identity/bank/company данных через API сбрасывает `is_verified` в `False`. Источник: `users/serializers/artist_legal_profile.py: ArtistLegalSerializer.update`.

**Зависит от настройки:** проверка обязательных согласий может быть глобально отключена. Когда она включена, наборы по сценариям заданы в `ConsentPolicy`: регистрация слушателя требует listener offer/personal data/distribution; регистрация артиста/лейбла дополнительно требует соответствующие artist-документы; newsletter-согласия необязательны. Источники: `users/consents_policy.py`, `users/services/consent.py: ConsentService.validate`.

**Подтверждено:** новое согласие можно создать только на активную версию документа. Отзыв не удаляет запись, а заполняет `revoked_at`. Повторные факты согласия разрешены; `skip_existing` применяется только в явно использующих его сценариях. Источники: `users/models/consents/user_consent.py`, `users/services/consent.py`.

### 4.3. Приглашение принять профиль артиста

**Подтверждено:** приглашать можно только на профиль типа `artist`, созданный без собственного аккаунта и принадлежащий лейблу, которым управляет инициатор. Email не должен уже принадлежать зарегистрированному пользователю; на один профиль существует не более одного claim. Источник: `users/services/invitation.py: ArtistProfileClaimInvitationService.create` и его проверки.

**Подтверждено:** принять приглашение может вошедший пользователь с тем же email, если у него ещё нет `ArtistProfile`. Принятие связывает аккаунт с профилем и одновременно подтверждает email. Источник: `users/services/invitation.py: accept`.

**Подтверждено:** повторная отправка после cooldown возможна для непринятого приглашения, включая `rejected`, `revoked` и `expired`; сервис обновляет токен, срок и возвращает статус в `pending`. Принятое приглашение переотправить или отозвать нельзя. Источник: `users/models/invitation.py: can_resend`, `users/services/invitation.py: resend, revoke, _renew_invitation`.

### 4.4. Публикация и видимость

**Подтверждено:** для обычного пользователя список показывает только активный опубликованный `public`-контент; detail также допускает `link_only`. `hidden` доступен управляющему пользователю и staff. Источники: `store/querysets/visibility.py`, `store/querysets/track_visibility.py`.

**Подтверждено:** дата релиза ограничивает публичные каталожные queryset альбомов, треков и связанного мерча: будущий `release_date` исключает объект. Источник: `store/querysets/product.py: published_albums, published_tracks, published_merch`.

**Подтверждено:** альбом нельзя опубликовать через API без хотя бы одного активного трека с непустым оригинальным аудиофайлом. Удаление или деактивация последнего такого трека снимает публикацию альбома. Источники: `store/services/album_publication.py`, `store/serializers/album.py`, `store/views/track.py`, `store/admin/forms/publication.py`.

**Подтверждено:** опубликованные альбом и мерч должны иметь цену больше нуля; это проверяется API/admin-логикой, но не DB check цены. Для отдельно продаваемого трека нулевая цена означает «нельзя приобрести отдельно от альбома». Источники: `store/views/mixins/commerce.py: _validate_publication_price`, `store/serializers/cart.py: CartItemWriteSerializer.validate`.

**Зависит от настройки:** когда включена проверка готовности к публикации, цифровому контенту нужны определённый получатель выплат, подтверждённый email и верифицированный юридический профиль получателя; физическому контенту дополнительно нужна эффективная настроенная точка отправки. При выключенной проверке эти условия не блокируют публикацию/покупку/публичный профиль. Источник: `common/services/ready_for_sales.py`.

**Подтверждено:** эффективный получатель выплат — пользователь лейбла для артиста под лейблом, иначе собственный пользователь артиста. Источник: `users/models/artist/profile.py: default_payout_recipient`.

**Подтверждено:** собственная включённая доставка артиста имеет приоритет. Если она включена, но точка не настроена, fallback на лейбл не выполняется. Fallback к доставке лейбла работает только когда собственная настройка отсутствует или выключена. Аналогично выбираются точки самовывоза. Источник: `users/models/artist/profile.py: effective_shipping_point, get_effective_pickup_points`.

### 4.5. Товар и варианты

**Подтверждено:** штатные create/update контента вызывают `ProductService`. Для альбома и трека создаётся один цифровой вариант с `property_value='digital'`, `stock=NULL`. Для мерча без свойства создаётся `simple`; с `property_name` синхронизируется список вариантов, а отсутствующие в новом списке деактивируются. Источники: `store/views/mixins/commerce.py`, `store/services/commerce.py`.

**Подтверждено:** значения `simple` и `digital` зарезервированы и недоступны как пользовательское имя свойства/варианта. В одном запросе варианты не должны дублироваться; ID изменяемого варианта обязан принадлежать товару. Источники: `store/serializers/merch.py`, `store/services/commerce.py: sync_merch_variants`.

**Подтверждено:** вариант доступен для покупки только если активны вариант, контент и объект публикации; публикация включена; видимость `public` или `link_only`; цена больше нуля; выполнена применимая готовность артиста; для мерча остаток `NULL` или больше нуля. У трека объект публикации — его альбом. Источник: `store/models/product_variant.py: is_available_for_purchase`.

### 4.6. Корзина, checkout и заказ

**Подтверждено:** при чтении корзины недоступные варианты удаляются. При объединении гостевой и пользовательской корзин недоступные позиции пропускаются; цифровое количество ограничивается единицей, количество мерча — текущим остатком. Источники: `store/services/cart_service.py: remove_unavailable_items, merge_carts`.

**Подтверждено:** `price_with_donation` учитывается только если у продукта `allow_overpay=True`; валидация не допускает доплату ниже базовой цены. Источники: `store/models/cart_item.py`, `store/validators.py: validate_price_with_donation`.

**Подтверждено:** промокод применяется только к товарам своего артиста. Если он перестал быть доступен или в корзине больше нет подходящих товаров, связь с корзиной снимается. Использование инкрементируется при резервировании и декрементируется при снятии резерва. Источники: `store/services/cart_service.py: validate_cart_promocode`, `store/services/inventory.py`.

**Подтверждено:** текущий checkout API требует аутентификацию, непустую корзину и повторно проверяет доступность товаров. Для корзины только с цифровым контентом доставка очищается. Для мерча обязателен активный способ доставки и набор полей, соответствующий `courier`, `pickpoint` или `artist_pickup`; выбранная точка самовывоза должна входить в доступные для текущей корзины. Источники: `store/views/order.py: checkout`, `store/serializers/checkout.py`.

**Подтверждено:** checkout создаёт снимки цен, скидок, продавца, получателя выплат и описания товара, очищает корзину, затем резервирует мерч и промокод на ограниченный срок. Источники: `store/services/order_service.py`, `store/views/order.py`, `store/services/inventory.py`.

**Подтверждено:** доступ к купленной музыке вычисляется SQL views. Прямо купленный трек доступен для заказов `paid`/`completed`; треки купленного альбома — также; треки носителя — при `paid`/`shipped`/`completed`, если `MerchKind.is_carrier=True` и мерч связан с альбомом. Источники: `store/migrations/sql/views/listener_track_access_v1.sql`, `listener_album_access_v1.sql`.

### 4.7. Аудио, архивы, отчёты и выплаты

**Подтверждено:** прямая загрузка сначала создаёт технический `Track` без файла и позиции, а также товар. После успешного переноса файла новому треку присваивается позиция после максимальной занятой и запускаются подготовка аудио и пересборка архива. Источники: `store/services/track_upload/upload_service.py`, `store/services/track_upload/upload_storage.py`.

**Подтверждено:** обработчик определяет длительность оригинала и независимо готовит приватный stream и публичный preview. Для короткого трека preview равен всему треку; для длинного собирается из начала и фрагмента оставшейся части. Источники: `store/services/audio/preparation.py`, `store/services/audio/processing.py`.

**Подтверждено:** архив планируется только для опубликованного альбома с активными треками. Его актуальность определяется хешем ID альбома, пути обложки и для каждого активного трека — ID, позиции, имени и пути оригинала. Изменение состава делает прежний архив неактуальным; готовый ZIP содержит обложку и оригиналы. Источник: `store/services/album_archive.py`.

**Подтверждено:** отчёт агрегирует позиции по первому успешному платежу заказа в периоде и конкретному `payout_recipient`, рассчитывает продажи, доплаты, скидки, комиссию и сумму выплаты. После готовности PDF создаётся или синхронизируется выплата. Источники: `store/services/report.py`, `store/tasks/report.py`, `store/services/payout.py`.

## 5. Состояния и переходы

### 5.1. Профили и верификация

| Объект | Переход | Как происходит |
|---|---|---|
| `ArtistProfile.profile_type` | отсутствие профиля → `artist` или `label` | регистрация или onboarding |
| `ArtistProfile.profile_type` | `artist` → `label` | только для активного независимого артиста |
| `ArtistProfile.profile_type` | `label` → `artist` | **не определён / не реализован** |
| `ArtistProfile.is_active` | active ↔ inactive | поле существует; отдельный пользовательский transition API не найден |
| `ArtistLegalProfile.is_verified` | false → true | административная верификация |
| `ArtistLegalProfile.is_verified` | true → false | любое изменение юридических данных через API |
| email/phone verification | false → true | соответствующая проверка; принятие claim также подтверждает email |
| phone verification | true → false | смена номера телефона |

Источники: `users/serializers/artist_profile.py`, `users/serializers/artist_legal_profile.py`, `users/serializers/account.py`, `users/services/invitation.py`.

### 5.2. Приглашение

Подтверждённые переходы:

```text
pending ──accept──> accepted
pending ──reject──> rejected
pending ──revoke──> revoked
pending ──expiry/read or scheduled task──> expired
rejected | revoked | expired ──resend after cooldown──> pending
```

`accepted` — финальное состояние для операций resend/revoke. Источники: `users/services/invitation.py`, `users/tasks/invitation.py`.

### 5.3. Публикация контента

Контент одновременно имеет независимые оси:

- активность: `is_active` / inactive;
- публикация: draft (`is_published=False`) / published;
- видимость: `public` / `link_only` / `hidden`.

Публикация и снятие с публикации поддерживаются в обе стороны. Альбом автоматически становится draft, если исчезает последний активный загруженный трек. Деактивация не равна снятию публикации в данных, но исключает объект из обычных публичных выборок. Источники: `store/models/abstract/visibility_model.py`, `store/querysets/visibility.py`, `store/services/album_publication.py`.

### 5.4. Загрузка и обработка файлов

`TrackUpload`:

```text
initiated ──локальная передача──> uploaded ──complete──> completed
initiated ──S3 upload + complete──> completed
initiated ──истечение срока при приёме──> expired
```

`failed` объявлен в choices, но явного перехода в него в просмотренных сервисах нет. Cleanup удаляет старые незавершённые технические треки без оригинала, если upload не `completed`. Источники: `store/services/track_upload/upload_service.py`, `upload_storage.py`, `clean_up.py`.

`TrackGeneratedAudio` для preview и stream:

```text
pending/ready/failed ──новый запуск──> building ──успех──> ready
                                      └─ошибка──> failed
```

Замена оригинала запускает обработку повторно. Источники: `store/services/audio/schedule.py`, `store/services/audio/preparation.py`.

`AlbumArchive`:

```text
pending ──worker starts──> building ──успех──> ready
                              └─ошибка──> failed
ready/failed/building ──изменился актуальный состав──> pending
```

Если активных треков нет, архив инвалидируется: файл очищается, статус становится `pending`, но новая сборка не ставится. Источник: `store/services/album_archive.py`.

### 5.5. Заказ и оплата

Основной автоматизированный путь:

```text
created ──reserve at checkout──> reserved ──successful payment──> paid
reserved ──expired without pending payment──> canceled
paid ──manual/admin logistics──> shipped ──manual/admin──> completed
```

Важные детали:

- платеж создаётся только для `reserved`; для `created`, `paid` и прочих состояний сервис возвращает отдельный результат без создания нормального платёжного сценария;
- успешный webhook переводит `Payment` в `succeeded`, заполняет `paid_at`, переводит заказ в `paid` и снимает срок резерва;
- отмена провайдером переводит платеж в `canceled`, но сама по себе не переводит заказ из `reserved`;
- фоновое снятие истёкшего резерва пропускает заказ, пока есть `pending`-платёж;
- админка позволяет менять статус заказа шире показанного основного пути. Она резервирует остатки при переходе из `{created,canceled}` в `{reserved,paid,shipped,completed}` и возвращает их при обратном переходе; строгого графа допустимых пар переходов нет.

Источники: `store/views/order.py`, `store/services/inventory.py`, `store/services/payment.py`, `store/tasks/reservations.py`, `store/admin/hooks/order_hooks.py`.

`Payment`: штатно `pending → succeeded` или `pending → canceled`. `failed` объявлен, но явный переход в него в просмотренном платёжном сервисе не найден. Повтор после отмены может создать новый pending-платёж. Источник: `store/services/payment.py`.

`Shipment`: создаётся как `CREATED`; внешний сервис может вернуть `ACCEPTED`/`WAITING`, задача продолжает ожидание; финал — `SUCCESSFUL` с номером накладной либо `INVALID`. Источники: `store/services/cdek.py: register_orders`, `store/tasks/cdek.py`.

### 5.6. Отчёт и выплата

```text
Report: pending ──PDF built──> ready
                └─final retry failed──> failed
        ready/failed ──regenerate──> pending

Payout: pending | on_hold | paid ──admin form──> любое из трёх состояний
        pending/on_hold ──admin action──> paid
```

При повторной генерации готового отчёта старый файл удаляется, данные пересчитываются, статус возвращается в `pending`. Выплата создаётся только для `ready`; уже `paid` выплата при синхронизации не изменяется. Для выплаты строгого графа переходов нет: административная форма допускает все значения choices. Она автоматически ставит `paid_at` при сохранении статуса `paid`; обратный переход не очищает дату автоматически. Источники: `store/services/report.py`, `store/tasks/report.py`, `store/services/payout.py`, `store/admin/payout.py`.

## 6. Проверки доступа, важные для интерфейсов

- Активный профиль слушателя требуется там, где используется permission `IsListener`; активный артист/лейбл — для `IsArtist`, `IsLabel`, `IsArtistOrLabel`. Источники: `common/permissions/base.py`, `common/permissions/profiles.py`.
- `IsUserVerified` считает аккаунт подтверждённым, если подтверждён **email или телефон**, не обязательно оба. Источник: `common/permissions/verification.py`.
- Право управлять артистом есть у собственного пользователя профиля или владельца его родительского лейбла. Источник: `common/access/artists.py`.
- Право управлять store-объектом определяется через `obj.artist` либо `obj.album.artist`. Источник: `common/access/store.py`.
- Важно: permission `CanCreateArtistContent` проверяет наличие профиля и его тип, но сам по себе не проверяет `profile.is_active`; конкретные view/mixin могут добавлять другие проверки. Источник: `common/permissions/profiles.py`.
- Заказы в пользовательском API видит только их владелец; текущий checkout требует аутентификацию. Источник: `store/views/order.py`.
- Режим просмотра черновиков каталога существует и зависит от настройки: доступ может быть открыт всем, только staff либо никому. Значение настройки конкретного окружения здесь не фиксируется. Источник: `common/access/store.py: can_preview_catalog_drafts`.

## 7. SQL views и поисковый индекс

### `listener_track_access`

Объединяет три источника прав: отдельный трек, альбом целиком, физический носитель связанного альбома. Права вычисляются из текущих связей товаров и статуса заказа, а не сохраняются отдельной записью покупки. Источники: `store/migrations/sql/views/listener_track_access_v1.sql`, модель `store/models/music_access.py`.

### `listener_album_access`

Создаёт строку для релиза, если пользователю доступен хотя бы один его трек. `is_fully_available=True`, когда в релизе не остаётся ни одного трека без доступа. В расчёт входят все строки `store_track` релиза без фильтра `is_active`. Источник: `store/migrations/sql/views/listener_album_access_v1.sql`.

### `catalog_search`

Материализованный индекс включает типы `album`, `track`, `merch`, `artist`. Он имеет уникальный индекс `(entity_type, entity_id)` и полнотекстовые/триграммные индексы. Для refresh существует фоновая задача, поэтому между изменением исходной сущности и её запуском индекс хранит прежнее состояние. `id` строится через `ROW_NUMBER()` и не является стабильным ID сущности. Публичный URL глобального поиска в текущем `store/urls.py` закомментирован, то есть этот поиск сейчас не является доступной API-возможностью. Источники: `store/migrations/sql/views/catalog_search_v1.sql`, `store/migrations/sql/views/catalog_search_v1_indexes.sql`, `store/models/catalog_search.py`, `store/tasks/catalog_search.py`, `store/urls.py`.

## 8. Известные ограничения текущей реализации

Ниже перечислены только наблюдаемые свойства текущего кода, без предложений по изменению.

### 8.1. Гарантии, существующие только в сервисном/API-слое

- БД не требует наличия `Product` и `ProductVariant` у каждого контентного объекта; это обеспечивает штатный `ProductService`. Источники: `store/models/product.py`, `store/services/commerce.py`.
- БД не запрещает опубликовать альбом без загруженных треков и не требует цену больше нуля; штатные API/admin это проверяют. Источники: `store/serializers/album.py`, `store/views/mixins/commerce.py`, `store/admin/forms/publication.py`.
- БД не проверяет соответствие `is_verified` полноте юридических данных; готовность вычисляется методом модели, а статус выставляется административно. Источник: `users/models/artist/legal_profile.py`.
- Не все обычные `clean()`-валидации автоматически гарантируются при `QuerySet.update`, `bulk_create` или прямой работе с ORM. Явный `full_clean()` встроен лишь в часть моделей, например consent/legal/cart. Источники: соответствующие `save()` в `users/models/consents/*.py`, `users/models/artist/*_data.py`, `store/models/cart.py`, `store/models/cart_item.py`.

### 8.2. Контент и каталог

- `Track` одновременно является аудиозаписью и позицией ровно одного `Album`; переиспользование одной записи в нескольких релизах моделью не представлено. Источник: `store/models/track.py`.
- Позиции треков nullable и не уникальны внутри альбома. Штатная загрузка и reorder упорядочивают их, но БД допускает пропуски и дубли. Источники: `store/models/track.py`, `store/services/track_upload/upload_storage.py`, `store/views/track.py`.
- `is_single` — только флаг релиза; ограничений на число треков сингла в модели и просмотренных сервисах нет. Источник: `store/models/album.py`.
- Основной смешанный каталог включает альбомы и мерч, но не треки; треки доступны отдельной выборкой и через релиз. Источник: `store/querysets/product.py: published_catalog_content, for_track_cards`.
- `ProductVariant.is_available_for_purchase` не проверяет `Album.release_date`, хотя публичные каталожные queryset её проверяют. Поэтому каталожная видимость будущего релиза и доступность варианта по прямому ID вычисляются разными наборами условий. Источники: `store/models/product_variant.py`, `store/querysets/product.py`.
- У `Merch.kind` есть расхождение DB/form-семантики: `NULL` допустим в БД, пустое значение не разрешено обычной Django-валидацией формы. Источник: `store/models/merch.py`.
- Уникальность главного изображения не учитывает `Image.is_active`: неактивное главное изображение продолжает занимать уникальный слот. Источник: `store/models/image.py`.

### 8.3. Состояния и асинхронность

- Для `Order` нет строгого конечного автомата на уровне модели; admin может перевести заказ между любыми choice-статусами, а hook только синхронизирует наличие резерва между двумя группами статусов. Источник: `store/admin/hooks/order_hooks.py`.
- `TrackUpload.failed` и `Payment.failed` объявлены, но явные переходы в эти состояния в основных просмотренных сервисах отсутствуют. Источники: `store/models/track.py`, `store/models/payment.py`, `store/services/track_upload/*.py`, `store/services/payment.py`.
- При ошибке именно подготовки preview обработчик в текущем коде записывает `FAILED` и текст ошибки в поля stream, а не preview. Это означает, что отображаемые состояния двух производных файлов могут не соответствовать фактически упавшему шагу. Источник: `store/services/audio/preparation.py: _prepare_preview`.
- Аудио, ZIP-архивы, отчёты, отправления и поисковый индекс готовятся асинхронно. Промежуточное состояние поэтому может штатно существовать без готового файла или внешнего номера. Источники: `store/tasks/audio.py`, `store/tasks/album_archive.py`, `store/tasks/report.py`, `store/tasks/cdek.py`, `store/tasks/catalog_search.py`.

### 8.4. Доступ и вычисляемые данные

- Доступ к музыке определяется текущими строками заказа и текущими связями `Product → Track/Album/Merch`; это не отдельный неизменяемый entitlement snapshot. Источник: `store/migrations/sql/views/listener_track_access_v1.sql`.
- `ListenerAlbumAccess.is_fully_available` учитывает также неактивные треки релиза. Источник: `store/migrations/sql/views/listener_album_access_v1.sql`.
- Поисковый `CatalogSearch.id` меняется между refresh; стабильной ссылкой служат `entity_type + entity_id`. Источник: `store/models/catalog_search.py`.
- Реализация глобального поиска и materialized view присутствует, но URL поиска отключён в текущей маршрутизации. Источник: `store/urls.py`.
- Готовность к публикации и доступность публичного профиля зависят от runtime-флага. Без знания значения флага нельзя утверждать, что в конкретном окружении юридическая верификация сейчас блокирует публикацию. Источник: `common/services/ready_for_sales.py`.
- Возможность предпросмотра черновиков также зависит от runtime-режима и не выводится из данных пользователя/контента без этой настройки. Источник: `common/access/store.py`.

## 9. Что остаётся неопределённым

- Не определён пользовательский сценарий реактивации деактивированных `ListenerProfile` и `ArtistProfile`; поле и административное управление существуют, отдельного публичного перехода в просмотренном API нет.
- Не определён обратный переход профиля `label → artist`.
- Не определён штатный переход в `Payment.failed` и `TrackUpload.failed`.
- Статусы `shipped` и `completed` заказа меняются административно; автоматической привязки этих статусов к состоянию всех `Shipment` в просмотренном коде нет.
- `Payout.on_hold` и возвраты из `paid` не имеют отдельного доменного сервиса; изменение доступно через административную модельную форму.
- Фактическое включение проверок обязательных согласий, готовности публикации и режима draft preview зависит от конфигурации окружения и намеренно не фиксируется в этом справочнике.

Источники неопределённостей: перечисления и сервисы в `users/models/artist/profile.py`, `store/models/order.py`, `store/models/payment.py`, `store/models/payout.py`, `store/models/track.py`; административные сценарии — `store/admin/order.py`, `store/admin/payout.py`; feature-dependent поведение — `users/services/consent.py`, `common/services/ready_for_sales.py`, `common/access/store.py`.
