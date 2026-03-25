from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_coreuser_is_email_verified'),
    ]

    operations = [
        migrations.RenameField(
            model_name='artistprofile',
            old_name='owner',
            new_name='user',
        ),
        migrations.AlterField(
            model_name='artistprofile',
            name='user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='artist_profile',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Пользователь',
            ),
        ),
    ]
