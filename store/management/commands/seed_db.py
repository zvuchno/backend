from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from store.models import (
    Album,
    Cart,
    CartItem,
    Delivery,
    Favorite,
    Genre,
    Image,
    Merch,
    MerchKind,
    Product,
    ProductVariant,
    Track,
)

User = get_user_model()


class Command(BaseCommand):
    """Менеджер команды для заполнения базы данными."""

    help = 'Заполняет базу данных тестовыми данными'

    def add_arguments(self, parser):
        parser.add_argument(
            'total',
            nargs='?',
            type=int,
            default=20,
            help='Количество создаваемых объектов.',
        )

    def handle(self, *args, **options):
        total = options['total']
        self.stdout.write(f'Процесс заполнение БД. Цель: {total} объектов')

        # ----------Начальные данные----------
        # Пользователь
        user = User.objects.create(
            username='vasya_pupkin',
            email='vasya@example.com',
        )

        # Жанры
        genres_data = [
            {'name': 'Rock', 'slug': 'rock'},
            {'name': 'Hip-Hop', 'slug': 'hip-hop'},
            {'name': 'Electronic', 'slug': 'electronic'},
        ]

        genres = [
            Genre.objects.get_or_create(**data)[0] for data in genres_data
        ]
        # Типы мерча
        merch_kinds = [
            MerchKind.objects.get_or_create(name=name)[0]
            for name in ['Футболка', 'Кружка', 'Постер']
        ]
        # Корзина
        cart = Cart.objects.create(
            user=user,
        )
        # Альбом
        album = Album.objects.get_or_create(
            genre=genres[0],
            owner=user,
        )[0]

        # ----------Массовые данные----------
        created = 0
        for i in range(total):
            track = Track.objects.create(
                name=f'product_{i}',
                duration=100,
                album=album,
                owner=user,
            )
            product = Product.objects.create(
                price=Decimal(100),
                track=track,
            )
            track.product = product
            track.save()

            album = Album.objects.get_or_create(
                name=f'album_{i}',
                genre=genres[0],
                owner=user,
            )[0]
            product = Product.objects.create(
                price=Decimal(100),
                album=album,
            )
            album.product = product
            album.save()

            merch = Merch.objects.create(
                name=f'merch_{i}',
                kind=merch_kinds[0],
                owner=user,
            )
            product = Product.objects.create(
                price=Decimal(100),
                merch=merch,
            )
            merch.product = product
            merch.save()

            Image.objects.create(
                merch=merch,
            )

            product_variant = ProductVariant.objects.get_or_create(
                product=product,
                stock=100,
            )[0]

            Favorite.objects.create(
                user=user,
                product_variant=product_variant,
            )

            CartItem.objects.create(
                cart=cart,
                product_variant=product_variant,
                quantity=1,
            )

            Delivery.objects.create(
                name=f'delivery_{i}',
                price=100,
            )

            created += 1
            self.stdout.write(f'Создано {created} / {total}', ending='\r')

        self.stdout.write(self.style.SUCCESS(f'Создано {created} объектов'))
