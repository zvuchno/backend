"""
Product
    ├ Track
    ├ Album
    └ Merch
        │
        ▼
        ProductVariant (SKU, price, stock, characteristics)


Cart
└ CartItem → ProductVariant

Favorite
└ Favorite → ProductVariant

Order
└ OrderItem → ProductVariant
 """


class Product(ActivatableModel, TimestampModel, VisibilityModel):
    """
    Это универсальная карточка товара.

    ProductType тут не обязателен, но может быть удобен,
    например для фильтрации:
    products = Product.objects.filter(type='track').select_related('track')
    или
    if product.type == Product.ProductType.MERCH:
        deliver_shipping()
    """
    class ProductType(models.TextChoices):
        TRACK = 'track', 'Track'
        ALBUM = 'album', 'Album'
        MERCH = 'merch', 'Merch'

    type = models.CharField(max_length=20, choices=ProductType.choices)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)
    base_price = models.DecimalField(null=True, blank=True, ...)
    allow_fans_overpay = models.BooleanField(default=False)

# Это реальный SKU
class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants'
    )
    sku = models.CharField(max_length=100, unique=True)
    # Здесь на будущее можно добавить цену варианта,
    # если не указана - берем из продукта
    price = models.DecimalField(null=True, blank=True, ...)
    characteristic = models.JSONField(...)
    # Наличие (этохарактеристика SKU)
    stock = models.PositiveIntegerField(default=0)


class Album(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='album'
    )
    cover = models.ImageField(...)


class Track(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name='track'
    )
    audio_file = models.FileField(...)


class Merch(models.Model):
    product = models.OneToOneField(Product, ...)
    category = models.ForeignKey(Category, ...)
    kind = models.ForeignKey(Kind, ...)


class Cart(TimestampModel):
    user = models.OneToOneField(User, ...)

    
# Корзина хранит вариант, а не продукт
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, ...)
    variant = models.ForeignKey(ProductVariant, ...)
    quantity = models.PositiveIntegerField(default=1)


class Favorite(models.Model):

    variant = models.ForeignKey(ProductVariant, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,)


# И потом заказ, тут тоже variant
class OrderItem(models.Model):
    order = models.ForeignKey(Order, ...)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(...)  # Цена перезаписывается


# Product — это маркетинговая сущность
# Variant — это складская сущность
