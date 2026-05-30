"""Сопоставление сущностей payload с сущностями API."""

from __future__ import annotations

import hashlib

from .constants import FIXTURE_NAMESPACE, MERCH_KIND_ALIASES


def normalize_username(source: str) -> str:
    """Нормализует строку для использования в username или имени файла."""
    return ''.join(
        char if char.isalnum() else '-' for char in source.lower()
    ).strip('-')


def marker(kind: str, *parts: object) -> str:
    """Формирует fixture-маркер для поиска ранее созданных объектов."""
    raw = ':'.join(str(part) for part in parts)
    return f'[fixture:{FIXTURE_NAMESPACE}:{kind}:{raw}]'


def marker_id_by_description(
    items: list[dict],
    kind: str,
) -> dict[str, int]:
    """Возвращает id объектов по fixture-маркерам из description."""
    prefix = f'[fixture:{FIXTURE_NAMESPACE}:{kind}:'
    result: dict[str, int] = {}

    for item in items:
        description = str(item.get('description', ''))
        item_id = item.get('id')
        if not item_id:
            continue

        start = description.find(prefix)
        end = description.find(']', start + 1)
        if start >= 0 and end > start:
            result[description[start : end + 1]] = item_id

    return result


def normalize_merch_kind(value: str) -> str:
    """Нормализует slug/name типа мерча или жанра для сопоставления."""
    return ''.join(char for char in value.lower() if char.isalnum())


def build_normalized_candidates(
    items: list[dict],
) -> list[tuple[int, list[str]]]:
    """Готовит список кандидатов для сопоставления по slug/name."""
    candidates = []

    for item in items:
        item_id = item.get('id')
        if not item_id:
            continue

        values = [
            str(item.get('slug', '')),
            str(item.get('name', '')),
        ]
        normalized_values = [
            normalize_merch_kind(value) for value in values if value
        ]
        candidates.append((item_id, normalized_values))

    return candidates


def find_lookup_match(
    candidates: list[tuple[int, list[str]]],
    normalized_aliases: set[str],
) -> int | None:
    """Ищет совпадение сначала точно, затем частично."""
    for item_id, normalized_values in candidates:
        if any(value in normalized_aliases for value in normalized_values):
            return item_id

    for item_id, normalized_values in candidates:
        if any(
            alias in value or value in alias
            for value in normalized_values
            for alias in normalized_aliases
        ):
            return item_id

    return None


def fallback_lookup_id(
    candidates: list[tuple[int, list[str]]],
    seed: str,
) -> int:
    """Возвращает стабильный fallback id по seed."""
    digest = hashlib.sha256(seed.encode('utf-8')).hexdigest()
    fallback_index = int(digest[:8], 16) % len(candidates)
    return candidates[fallback_index][0]


def match_merch_kinds(items: list[dict]) -> dict[str, int]:
    """Сопоставляет канонические типы мерча с типами, найденными в API."""
    candidates = build_normalized_candidates(items)
    matched: dict[str, int] = {}

    for canonical, aliases in MERCH_KIND_ALIASES.items():
        normalized_aliases = {
            normalize_merch_kind(alias) for alias in (canonical, *aliases)
        }
        item_id = find_lookup_match(candidates, normalized_aliases)
        if item_id is not None:
            matched[canonical] = item_id

    return matched


def match_genres(
    items: list[dict],
    genres_payload: list[dict],
) -> dict[str, int]:
    """Сопоставляет жанры payload с жанрами, доступными через API."""
    candidates = build_normalized_candidates(items)

    if not candidates:
        raise RuntimeError(
            'No genres found in API. Create genres before HTTP import.',
        )

    matched: dict[str, int] = {}

    for genre in genres_payload:
        genre_slug = genre['slug']
        normalized_aliases = {
            normalize_merch_kind(str(genre.get('slug', ''))),
            normalize_merch_kind(str(genre.get('name', ''))),
        }
        normalized_aliases.discard('')

        genre_id = find_lookup_match(candidates, normalized_aliases)
        if genre_id is None:
            genre_id = fallback_lookup_id(candidates, genre_slug)

        matched[genre_slug] = genre_id

    return matched
