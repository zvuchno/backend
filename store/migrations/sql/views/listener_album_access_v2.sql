CREATE VIEW listener_album_access AS

-- Альбомы с хотя бы одним доступным треком.
WITH available_album AS (
    SELECT DISTINCT
        lta.user_id,
        release_track.release_id AS album_id
    FROM listener_track_access lta
    JOIN store_releasetrack release_track
        ON release_track.id = lta.track_id
)
-- Нет недоступных треков в альбоме.
SELECT
    available_album.user_id,
    available_album.album_id,
    NOT EXISTS (
        SELECT 1
        FROM store_releasetrack album_track
        WHERE
            album_track.release_id = available_album.album_id
            AND NOT EXISTS (
                SELECT 1
                FROM listener_track_access track_access
                WHERE
                    track_access.user_id = available_album.user_id
                    AND track_access.track_id = album_track.id
            )
    ) AS is_fully_available
FROM available_album;
