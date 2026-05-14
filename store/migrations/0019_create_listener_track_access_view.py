from django.db import migrations


CREATE_VIEW = """
CREATE VIEW listener_track_access AS

-- Сгенерировать id для Django ORM.
SELECT
    CONCAT(user_id, '-', track_id) AS id,
    user_id,
    track_id

-- Объединенные user_id и track_id из трех источников доступа.
FROM (

    -- Купленные треки.
    SELECT
        o.user_id,
        p.track_id
    FROM store_order o
    JOIN store_orderitem oi ON oi.order_id = o.id
    JOIN store_productvariant pv ON pv.id = oi.product_variant_id
    JOIN store_product p ON p.id = pv.product_id
    WHERE o.user_id IS NOT NULL
      -- Куплен трек.
      AND o.status IN ('paid', 'completed')
      AND p.track_id IS NOT NULL

    UNION

    -- Треки из купленных альбомов.
    SELECT
        o.user_id,
        t.id AS track_id
    FROM store_order o
    JOIN store_orderitem oi ON oi.order_id = o.id
    JOIN store_productvariant pv ON pv.id = oi.product_variant_id
    JOIN store_product p ON p.id = pv.product_id
    -- Треки альбома.
    JOIN store_track t ON t.album_id = p.album_id
    WHERE o.user_id IS NOT NULL
      AND o.status IN ('paid', 'completed')
      -- Куплен альбом.
      AND p.album_id IS NOT NULL

    UNION

    -- Треки из купленных носителей.
    SELECT
        o.user_id,
        t.id AS track_id
    FROM store_order o
    JOIN store_orderitem oi ON oi.order_id = o.id
    JOIN store_productvariant pv ON pv.id = oi.product_variant_id
    JOIN store_product p ON p.id = pv.product_id
    JOIN store_merch m ON m.id = p.merch_id
    -- Треки из альбома связанного с мерчом.
    JOIN store_track t ON t.album_id = m.album_id
    WHERE o.user_id IS NOT NULL
      AND o.status IN ('paid', 'shipped', 'completed')
      AND p.merch_id IS NOT NULL
      -- Куплен именно носитель альбома.
      AND m.album_id IS NOT NULL
      AND m.is_carrier = TRUE
) listener_access;
"""

DROP_VIEW = """
DROP VIEW IF EXISTS listener_track_access;
"""


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0018_delivery_delivery_type'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_VIEW,
            reverse_sql=DROP_VIEW,
        ),
    ]
