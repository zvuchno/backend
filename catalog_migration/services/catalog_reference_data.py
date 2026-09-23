"""Reference values required by the catalog migration runtime."""

MERCH_KINDS = [
    {'name': name, 'slug': slug, 'is_carrier': is_carrier}
    for name, slug, is_carrier in [
        ('CD', 'cd', True),
        ('Винил', 'vinyl', True),
        ('Кассета', 'cassette', True),
        ('Аксессуары', 'accessories', False),
        ('Другое', 'other', False),
        ('Наборы', 'bundles', False),
        ('Одежда', 'clothing', False),
        ('Полиграфия', 'print', False),
        ('Стикеры', 'stickers', False),
    ]
]

GENRES = [
    {'name': name, 'slug': slug}
    for name, slug in [
        ('Поп', 'pop'),
        ('Рэп / Хип-хоп', 'rap-hip-hop'),
        ('Рок', 'rock'),
        ('Инди', 'indie'),
        ('Электронная музыка', 'electronic'),
        ('Ambient', 'ambient'),
        ('Фонк', 'phonk'),
        ('R&B / Соул', 'rnb-soul'),
        ('Фолк / Этника', 'folk-ethnic'),
        ('Джаз / Блюз', 'jazz-blues'),
        ('Академическая', 'classical'),
        ('Шансон', 'chanson'),
        ('Другое', 'other'),
    ]
]
