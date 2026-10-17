CREATE VIEW listener_track_access AS

SELECT
    user_id,
    track_id,
    recording_id

-- Объединенные user_id и track_id из трех источников доступа.
FROM (

    -- Купленные треки.
    SELECT
        o.user_id,
        rt.id AS track_id,
        rt.recording_id
    FROM store_order o
    JOIN store_orderitem oi ON oi.order_id = o.id
    JOIN store_productvariant pv ON pv.id = oi.product_variant_id
    JOIN store_product p ON p.id = pv.product_id
    JOIN store_releasetrack rt ON rt.id = p.track_id
    WHERE o.user_id IS NOT NULL
      -- Куплен трек.
      AND o.status IN ('paid', 'completed')
      AND p.track_id IS NOT NULL

    UNION

    -- Треки из купленных альбомов.
    SELECT
        o.user_id,
        rt.id AS track_id,
        rt.recording_id
    FROM store_order o
    JOIN store_orderitem oi ON oi.order_id = o.id
    JOIN store_productvariant pv ON pv.id = oi.product_variant_id
    JOIN store_product p ON p.id = pv.product_id
    -- Треки альбома.
    JOIN store_releasetrack rt ON rt.release_id = p.album_id
    WHERE o.user_id IS NOT NULL
      AND o.status IN ('paid', 'completed')
      -- Куплен альбом.
      AND p.album_id IS NOT NULL

    UNION

    -- Треки из купленных носителей.
    SELECT
        o.user_id,
        rt.id AS track_id,
        rt.recording_id
    FROM store_order o
    JOIN store_orderitem oi ON oi.order_id = o.id
    JOIN store_productvariant pv ON pv.id = oi.product_variant_id
    JOIN store_product p ON p.id = pv.product_id
    JOIN store_merch m ON m.id = p.merch_id
    JOIN store_merchkind mk ON mk.id = m.kind_id
    -- Треки из альбома, связанного с мерчом.
    JOIN store_releasetrack rt ON rt.release_id = m.album_id
    WHERE o.user_id IS NOT NULL
      AND o.status IN ('paid', 'shipped', 'completed')
      AND p.merch_id IS NOT NULL
      -- Куплен именно носитель альбома.
      AND m.album_id IS NOT NULL
      AND mk.is_carrier = TRUE
) listener_access;
