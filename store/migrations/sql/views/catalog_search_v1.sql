CREATE MATERIALIZED VIEW catalog_search AS
SELECT
    ROW_NUMBER() OVER () AS id,
    combined.*
FROM (

WITH available_products AS (

    -- ========================================================
    -- ALBUMS
    -- ========================================================

    SELECT DISTINCT
        product.id AS product_id,

        (
            COALESCE(payout_user.is_email_verified, FALSE) = TRUE
            AND COALESCE(legal_profile.is_verified, FALSE) = TRUE
        ) AS is_publication_ready

    FROM store_product product

    JOIN store_album album
        ON album.id = product.album_id

    JOIN users_artistprofile artist
        ON artist.id = album.artist_id

    LEFT JOIN users_artistprofile label
        ON label.id = artist.label_id

    JOIN users_coreuser payout_user
        ON payout_user.id = COALESCE(
            label.user_id,
            artist.user_id
        )

    LEFT JOIN users_artistlegalprofile legal_profile
        ON legal_profile.user_id = payout_user.id

    JOIN store_productvariant variant
        ON variant.product_id = product.id

    WHERE
        product.product_type = 'album'

        AND variant.is_active = TRUE

        AND album.is_active = TRUE
        AND album.is_published = TRUE
        AND album.visibility IN ('public', 'link_only')

        AND artist.is_active = TRUE

    UNION ALL

    -- ========================================================
    -- TRACKS
    -- ========================================================

    SELECT DISTINCT
        product.id AS product_id,

        (
            COALESCE(payout_user.is_email_verified, FALSE) = TRUE
            AND COALESCE(legal_profile.is_verified, FALSE) = TRUE
        ) AS is_publication_ready

    FROM store_product product

    JOIN store_track track
        ON track.id = product.track_id

    JOIN store_album album
        ON album.id = track.album_id

    JOIN users_artistprofile artist
        ON artist.id = album.artist_id

    LEFT JOIN users_artistprofile label
        ON label.id = artist.label_id

    JOIN users_coreuser payout_user
        ON payout_user.id = COALESCE(
            label.user_id,
            artist.user_id
        )

    LEFT JOIN users_artistlegalprofile legal_profile
        ON legal_profile.user_id = payout_user.id

    JOIN store_productvariant variant
        ON variant.product_id = product.id

    WHERE
        product.product_type = 'track'

        AND variant.is_active = TRUE

        AND track.is_active = TRUE

        AND album.is_active = TRUE
        AND album.is_published = TRUE
        AND album.visibility IN ('public', 'link_only')

        AND artist.is_active = TRUE

        AND product.price > 0

    UNION ALL

    -- ========================================================
    -- MERCH
    -- ========================================================

    SELECT DISTINCT
        product.id AS product_id,

        (
            COALESCE(payout_user.is_email_verified, FALSE) = TRUE
            AND COALESCE(legal_profile.is_verified, FALSE) = TRUE
        ) AS is_publication_ready

    FROM store_product product

    JOIN store_merch merch
        ON merch.id = product.merch_id

    JOIN users_artistprofile artist
        ON artist.id = merch.artist_id

    LEFT JOIN users_artistprofile label
        ON label.id = artist.label_id

    JOIN users_coreuser payout_user
        ON payout_user.id = COALESCE(
            label.user_id,
            artist.user_id
        )

    LEFT JOIN users_artistlegalprofile legal_profile
        ON legal_profile.user_id = payout_user.id

    JOIN store_productvariant variant
        ON variant.product_id = product.id

    LEFT JOIN users_artistshippingpoint shipping_point
        ON shipping_point.artist_id = artist.id

    LEFT JOIN users_artistshippingpoint label_shipping_point
        ON label_shipping_point.artist_id = artist.label_id

    WHERE
        product.product_type = 'merch'

        AND variant.is_active = TRUE

        AND (
            variant.stock IS NULL
            OR variant.stock > 0
        )

        AND merch.is_active = TRUE
        AND merch.is_published = TRUE
        AND merch.visibility IN ('public', 'link_only')

        AND artist.is_active = TRUE

        AND (
            shipping_point.id IS NOT NULL
            OR label_shipping_point.id IS NOT NULL
        )
),

available_variants AS (
    SELECT
        variant.product_id,

        string_agg(
            NULLIF(variant.property_value, ''),
            ' '
            ORDER BY variant.property_value
        ) FILTER (
            WHERE variant.property_value NOT IN ('digital', 'simple')
        ) AS variant_values,

        MIN(variant.id) AS selected_variant_id

    FROM store_productvariant variant

    JOIN store_product product
        ON product.id = variant.product_id

    WHERE
        variant.is_active = TRUE

        AND variant.product_id IN (
            SELECT product_id
            FROM available_products
        )

        AND (
            product.product_type IN ('album', 'track')

            OR (
                product.product_type = 'merch'
                AND (
                    variant.stock IS NULL
                    OR variant.stock > 0
                )
            )
        )

    GROUP BY variant.product_id
)

-- ============================================================
-- ALBUM
-- ============================================================

SELECT
    'album' AS entity_type,
    album.id AS entity_id,
    album.name AS name,
    artist.name AS artist_name,

    CASE
        WHEN album.is_single = TRUE THEN 'Сингл'::varchar
        ELSE 'Альбом'::varchar
    END AS kind,

    genre.name AS genre_name,
    NULL::varchar AS merch_kind_name,
    variants.variant_values,
    variants.selected_variant_id,
    NULL::bigint AS target_id,
    ap.is_publication_ready,

    album.cover_image AS image,

    concat_ws(
        ' ',
        album.name,
        artist.name,
        genre.name
    ) AS search_text,

    to_tsvector(
        'simple',
        concat_ws(
            ' ',
            album.name,
            artist.name,
            genre.name
        )
    ) AS search_vector

FROM store_album album

JOIN users_artistprofile artist
    ON artist.id = album.artist_id

LEFT JOIN store_genre genre
    ON genre.id = album.genre_id

JOIN store_product product
    ON product.album_id = album.id

JOIN available_products ap
    ON ap.product_id = product.id

JOIN available_variants variants
    ON variants.product_id = product.id

WHERE
    product.product_type = 'album'

UNION ALL

-- ============================================================
-- TRACK
-- ============================================================

SELECT
    'track' AS entity_type,
    track.id AS entity_id,
    track.name AS name,
    artist.name AS artist_name,
    'Трек'::varchar AS kind,

    genre.name AS genre_name,
    NULL::varchar AS merch_kind_name,
    variants.variant_values,
    variants.selected_variant_id,
    album.id AS target_id,
    ap.is_publication_ready,

    album.cover_image AS image,

    concat_ws(
        ' ',
        track.name,
        artist.name,
        genre.name
    ) AS search_text,

    to_tsvector(
        'simple',
        concat_ws(
            ' ',
            track.name,
            artist.name,
            genre.name
        )
    ) AS search_vector

FROM store_track track

JOIN store_album album
    ON album.id = track.album_id

JOIN users_artistprofile artist
    ON artist.id = album.artist_id

LEFT JOIN store_genre genre
    ON genre.id = album.genre_id

JOIN store_product product
    ON product.track_id = track.id

JOIN available_products ap
    ON ap.product_id = product.id

JOIN available_variants variants
    ON variants.product_id = product.id

WHERE
    product.product_type = 'track'

UNION ALL

-- ============================================================
-- MERCH
-- ============================================================

SELECT
    'merch' AS entity_type,
    merch.id AS entity_id,
    merch.name AS name,
    artist.name AS artist_name,
    merch_kind.name AS kind,

    NULL::varchar AS genre_name,
    merch_kind.name AS merch_kind_name,
    variants.variant_values,
    variants.selected_variant_id,
    NULL::bigint AS target_id,
    ap.is_publication_ready,

    (
        SELECT image.image
        FROM store_image image
        WHERE
            image.merch_id = merch.id
            AND image.is_active = TRUE
        ORDER BY
            image.is_main DESC,
            image.id
        LIMIT 1
    ) AS image,

    concat_ws(
        ' ',
        merch.name,
        artist.name,
        merch_kind.name
    ) AS search_text,

    to_tsvector(
        'simple',
        concat_ws(
            ' ',
            merch.name,
            artist.name,
            merch_kind.name
        )
    ) AS search_vector

FROM store_merch merch

JOIN users_artistprofile artist
    ON artist.id = merch.artist_id

LEFT JOIN store_merchkind merch_kind
    ON merch_kind.id = merch.kind_id

JOIN store_product product
    ON product.merch_id = merch.id

JOIN available_products ap
    ON ap.product_id = product.id

JOIN available_variants variants
    ON variants.product_id = product.id

WHERE
    product.product_type = 'merch'

UNION ALL

-- ============================================================
-- ARTIST
-- ============================================================

SELECT
    'artist' AS entity_type,
    artist.id AS entity_id,
    artist.name AS name,
    NULL::varchar AS artist_name,
    'Артист'::varchar AS kind,

    NULL::varchar AS genre_name,
    NULL::varchar AS merch_kind_name,
    NULL::text AS variant_values,
    NULL::bigint AS selected_variant_id,
    NULL::bigint AS target_id,
    NULL::boolean AS is_publication_ready,

    artist.cover AS image,

    artist.name AS search_text,

    to_tsvector(
        'simple',
        artist.name
    ) AS search_vector

FROM users_artistprofile artist

WHERE
    artist.is_active = TRUE

) AS combined;
