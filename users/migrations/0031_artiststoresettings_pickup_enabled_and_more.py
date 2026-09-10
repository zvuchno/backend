from django.db import migrations, models


def enable_existing_deliveries(apps, schema_editor):
    """Включает ранее настроенные способы доставки."""
    ArtistPickupPoint = apps.get_model(
        'users',
        'ArtistPickupPoint',
    )
    ArtistShippingPoint = apps.get_model(
        'users',
        'ArtistShippingPoint',
    )
    ArtistStoreSettings = apps.get_model(
        'users',
        'ArtistStoreSettings',
    )

    shipping_artist_ids = set(
        ArtistShippingPoint.objects
        .exclude(pvz_code='')
        .exclude(city_code='')
        .values_list('artist_id', flat=True)
    )

    pickup_artist_ids = set(
        ArtistPickupPoint.objects
        .filter(is_active=True)
        .values_list('artist_id', flat=True)
    )

    artist_ids = shipping_artist_ids | pickup_artist_ids

    for artist_id in artist_ids:
        settings, _ = ArtistStoreSettings.objects.get_or_create(
            artist_id=artist_id,
        )

        update_fields = []

        if artist_id in shipping_artist_ids:
            settings.shipping_enabled = True
            update_fields.append('shipping_enabled')

        if artist_id in pickup_artist_ids:
            settings.pickup_enabled = True
            update_fields.append('pickup_enabled')

        if update_fields:
            settings.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        (
            'users',
            '0030_alter_artistcontact_label_alter_artistsocial_label',
        ),
    ]

    operations = [
        migrations.AddField(
            model_name='artiststoresettings',
            name='pickup_enabled',
            field=models.BooleanField(
                default=False,
                verbose_name='Самовывоз включён',
            ),
        ),
        migrations.AddField(
            model_name='artiststoresettings',
            name='shipping_enabled',
            field=models.BooleanField(
                default=False,
                verbose_name='Доставка СДЭК включена',
            ),
        ),
        migrations.RunPython(
            enable_existing_deliveries,
            migrations.RunPython.noop,
        ),
    ]
