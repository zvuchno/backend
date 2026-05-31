"""Генерация связанных PNG-заглушек для тестового контента."""

from __future__ import annotations

import colorsys
import hashlib
import math
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageDraw

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class VisualStyle:
    """Детерминированная визуальная айдентика артиста."""

    background: RGB
    surface: RGB
    primary: RGB
    secondary: RGB
    accent: RGB
    dark: RGB
    light: RGB
    motif_type: int
    music_icon_type: int
    shirt_type: int


def _digest(*parts: object) -> bytes:
    raw = ':'.join(str(part) for part in parts)
    return hashlib.sha256(raw.encode('utf-8')).digest()


def _clamp(value: float) -> int:
    return max(0, min(255, int(value)))


def _mix(first: RGB, second: RGB, amount: float) -> RGB:
    return (
        _clamp(first[0] + (second[0] - first[0]) * amount),
        _clamp(first[1] + (second[1] - first[1]) * amount),
        _clamp(first[2] + (second[2] - first[2]) * amount),
    )


def _ellipse(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    **kwargs,
) -> None:
    """Рисует ellipse и нормализует координаты для маленьких размеров."""
    x0, y0, x1, y1 = box
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    if left == right:
        right += 1
    if top == bottom:
        bottom += 1
    draw.ellipse((left, top, right, bottom), **kwargs)


def _hsv(hue: float, saturation: float, value: float) -> RGB:
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
    return (_clamp(red * 255), _clamp(green * 255), _clamp(blue * 255))


def _artist_seed(seed: str) -> str:
    """Берет первую часть seed как основу стиля артиста."""
    return str(seed).split(':', 1)[0] or str(seed)


def _build_style(seed: str) -> VisualStyle:
    digest = _digest('artist-style', _artist_seed(seed))
    hue = digest[0] / 255
    secondary_hue = hue + 0.18 + digest[1] / 900
    accent_hue = hue + 0.47 + digest[2] / 1200

    background = _hsv(hue, 0.30 + digest[3] / 1100, 0.18 + digest[4] / 1800)
    surface = _hsv(
        hue + 0.04,
        0.16 + digest[5] / 1400,
        0.80 + digest[6] / 1800,
    )
    primary = _hsv(hue, 0.48 + digest[7] / 800, 0.60 + digest[8] / 1000)
    secondary = _hsv(
        secondary_hue,
        0.42 + digest[9] / 900,
        0.58 + digest[10] / 950,
    )
    accent = _hsv(
        accent_hue,
        0.52 + digest[11] / 850,
        0.74 + digest[12] / 1050,
    )
    dark = _mix(background, (0, 0, 0), 0.60)
    light = _mix(surface, (255, 255, 255), 0.28)

    return VisualStyle(
        background=background,
        surface=surface,
        primary=primary,
        secondary=secondary,
        accent=accent,
        dark=dark,
        light=light,
        motif_type=digest[13] % 6,
        music_icon_type=digest[14] % 5,
        shirt_type=digest[15] % 4,
    )


def _canvas(size: int, style: VisualStyle, salt: str) -> Image.Image:
    """Создает простой фон без шумовых точек."""
    digest = _digest('background', salt)
    top = _mix(style.background, style.primary, 0.18 + digest[0] / 1600)
    bottom = _mix(style.secondary, style.dark, 0.34 + digest[1] / 1400)
    img = Image.new('RGB', (size, size), top)
    draw = ImageDraw.Draw(img)

    band_count = 36
    band_height = max(size // band_count, 1)
    for y in range(0, size, band_height):
        amount = y / max(size - 1, 1)
        draw.rectangle(
            (0, y, size, min(size, y + band_height)),
            fill=_mix(top, bottom, amount),
        )

    return img


def _line_texture(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    color: RGB,
    seed: str,
) -> None:
    """Добавляет редкие линии, чтобы фон не выглядел плоско."""
    left, top, right, bottom = box
    width = right - left
    height = bottom - top
    digest = _digest('line-texture', seed)
    line_color = _mix(color, (255, 255, 255), 0.18)
    line_width = max(width // 140, 1)
    count = 3 + digest[0] % 4

    for index in range(count):
        y = top + digest[(index + 1) % len(digest)] % max(height, 1)
        offset = digest[(index + 7) % len(digest)] % max(width // 5, 1)
        draw.line(
            (left + offset, y, right - offset // 2, y + height // 14),
            fill=line_color,
            width=line_width,
        )


def _draw_music_icon(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    size: int,
    style: VisualStyle,
    seed: str,
) -> None:
    """Рисует простой музыкальный атрибут для альбомов и носителей."""
    x, y = center
    half = size // 2
    line = max(size // 12, 2)
    digest = _digest('music-icon', seed)
    icon_type = (style.music_icon_type + digest[0]) % 5
    color = _mix(style.light, style.accent, 0.25)
    shadow = _mix(style.dark, style.primary, 0.20)

    if icon_type == 0:
        # Нота.
        stem_x = x + half // 4
        draw.line(
            (stem_x, y - half, stem_x, y + half // 3),
            fill=color,
            width=line,
        )
        _ellipse(
            draw,
            (x - half, y, x, y + half),
            fill=color,
            outline=shadow,
            width=max(line // 3, 1),
        )
        draw.polygon(
            [
                (stem_x, y - half),
                (x + half, y - half + line),
                (x + half, y - half // 2),
                (stem_x, y - half // 2 - line),
            ],
            fill=color,
        )
    elif icon_type == 1:
        # Play.
        points = [
            (x - half // 2, y - half),
            (x - half // 2, y + half),
            (x + half, y),
        ]
        draw.polygon(points, fill=color)
        draw.line(points + [points[0]], fill=shadow, width=max(line // 3, 1))
    elif icon_type == 2:
        # Перемотка.
        first = [(x - half, y - half), (x - half, y + half), (x, y)]
        second = [(x, y - half), (x, y + half), (x + half, y)]
        draw.polygon(first, fill=color)
        draw.polygon(second, fill=color)
        draw.line(first + [first[0]], fill=shadow, width=max(line // 4, 1))
        draw.line(second + [second[0]], fill=shadow, width=max(line // 4, 1))
    elif icon_type == 3:
        # Эквалайзер.
        bars = 5
        gap = max(size // 18, 2)
        bar_w = max(size // 10, 3)
        start = x - (bars * bar_w + (bars - 1) * gap) // 2
        for index in range(bars):
            h = half // 2 + digest[index + 1] % max(half, 1)
            bx = start + index * (bar_w + gap)
            draw.rounded_rectangle(
                (bx, y + half - h, bx + bar_w, y + half),
                radius=bar_w // 2,
                fill=(style.primary, color, style.secondary)[index % 3],
            )
    else:
        # Кнопка record.
        _ellipse(
            draw,
            (x - half, y - half, x + half, y + half),
            fill=color,
            outline=shadow,
            width=line,
        )
        inner = half // 2
        _ellipse(
            draw,
            (x - inner, y - inner, x + inner, y + inner),
            fill=style.accent,
        )


def _motif_colors(
    style: VisualStyle,
) -> tuple[
    tuple[int, int, int],
    tuple[int, int, int],
    tuple[int, int, int],
    tuple[int, int, int],
]:
    """Возвращает основные цвета знака артиста."""
    main = style.accent
    second = style.primary
    shadow = _mix(style.dark, (0, 0, 0), 0.12)
    light = style.light
    return main, second, shadow, light


def _draw_motif_badge(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    size: int,
    style: VisualStyle,
    line: int,
) -> None:
    """Рисует подложку под знак артиста."""
    x, y = center
    half = size // 2
    pad = size // 11
    _ellipse(
        draw,
        (x - half - pad, y - half - pad, x + half + pad, y + half + pad),
        fill=_mix(style.surface, style.background, 0.10),
        outline=_mix(style.dark, style.primary, 0.18),
        width=max(line // 2, 1),
    )


def _draw_frontman_motif(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    size: int,
    style: VisualStyle,
    line: int,
) -> None:
    """Рисует знак артиста в виде фронтмена."""
    x, y = center
    half = size // 2
    main, second, shadow, light = _motif_colors(style)
    head = half // 4

    _ellipse(
        draw,
        (x - head, y - half, x + head, y - half + head * 2),
        fill=main,
        outline=shadow,
        width=max(line // 3, 1),
    )
    body = [
        (x, y - half + head * 2),
        (x + half // 2, y + half // 4),
        (x + half // 4, y + half),
        (x - half // 4, y + half),
        (x - half // 2, y + half // 4),
    ]
    draw.polygon(body, fill=second)
    draw.line(body + [body[0]], fill=shadow, width=max(line // 2, 1))
    draw.line(
        (x - half // 2, y - half // 8, x + half // 2, y - half // 8),
        fill=light,
        width=line,
    )


def _draw_plant_motif(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    size: int,
    style: VisualStyle,
    line: int,
) -> None:
    """Рисует знак артиста в виде растения."""
    x, y = center
    half = size // 2
    main, second, shadow, _light = _motif_colors(style)

    draw.line((x, y + half, x, y - half // 2), fill=shadow, width=line)
    leaf_positions = (y + half // 4, y - half // 8, y - half // 2)

    for direction in (-1, 1):
        for index, yy in enumerate(leaf_positions):
            leaf_w = half // 2 - index * max(half // 12, 1)
            if direction < 0:
                box = (
                    x - leaf_w,
                    yy - leaf_w // 2,
                    x - line,
                    yy + leaf_w // 2,
                )
            else:
                box = (
                    x + direction * line,
                    yy - leaf_w // 2,
                    x + direction * leaf_w,
                    yy + leaf_w // 2,
                )
            _ellipse(
                draw,
                box,
                fill=(main, second, style.accent)[index % 3],
                outline=shadow,
                width=max(line // 3, 1),
            )

    _ellipse(
        draw,
        (x - half // 5, y - half, x + half // 5, y - half + half // 3),
        fill=main,
    )


def _draw_mountain_motif(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    size: int,
    style: VisualStyle,
    line: int,
) -> None:
    """Рисует знак артиста в виде горы и солнца."""
    x, y = center
    half = size // 2
    main, second, shadow, light = _motif_colors(style)
    sun = half // 5

    _ellipse(
        draw,
        (
            x + half // 5,
            y - half,
            x + half // 5 + sun * 2,
            y - half + sun * 2,
        ),
        fill=light,
    )
    mountain = [
        (x - half, y + half),
        (x - half // 5, y - half // 2),
        (x + half // 8, y + half),
    ]
    mountain_2 = [
        (x - half // 6, y + half),
        (x + half // 2, y - half // 4),
        (x + half, y + half),
    ]
    draw.polygon(mountain, fill=second)
    draw.polygon(mountain_2, fill=main)
    draw.line(
        mountain + [mountain[0]],
        fill=shadow,
        width=max(line // 2, 1),
    )
    draw.line(
        mountain_2 + [mountain_2[0]],
        fill=shadow,
        width=max(line // 2, 1),
    )
    draw.polygon(
        [
            (x - half // 5, y - half // 2),
            (x - half // 3, y - half // 7),
            (x, y - half // 8),
        ],
        fill=light,
    )


def _draw_mascot_motif(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    size: int,
    style: VisualStyle,
    line: int,
) -> None:
    """Рисует знак артиста в виде маскота."""
    x, y = center
    half = size // 2
    main, _second, shadow, light = _motif_colors(style)

    face = (x - half, y - half // 2, x + half, y + half)
    ears = [
        [
            (x - half // 2, y - half // 3),
            (x - half // 5, y - half),
            (x, y - half // 3),
        ],
        [
            (x, y - half // 3),
            (x + half // 5, y - half),
            (x + half // 2, y - half // 3),
        ],
    ]
    for ear in ears:
        draw.polygon(ear, fill=main)
        draw.line(ear + [ear[0]], fill=shadow, width=max(line // 3, 1))

    _ellipse(
        draw,
        face,
        fill=main,
        outline=shadow,
        width=max(line // 2, 1),
    )
    eye = max(size // 24, 2)
    for ex in (x - half // 3, x + half // 3):
        _ellipse(draw, (ex - eye, y, ex + eye, y + eye * 2), fill=shadow)

    draw.polygon(
        [
            (x, y + half // 5),
            (x - eye, y + half // 3),
            (x + eye, y + half // 3),
        ],
        fill=light,
    )


def _draw_planet_motif(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    size: int,
    style: VisualStyle,
    line: int,
) -> None:
    """Рисует знак артиста в виде планеты."""
    x, y = center
    half = size // 2
    main, second, shadow, light = _motif_colors(style)

    _ellipse(
        draw,
        (x - half, y - half, x + half, y + half),
        fill=main,
        outline=shadow,
        width=line,
    )
    draw.arc(
        (
            x - half - half // 3,
            y - half // 2,
            x + half + half // 3,
            y + half // 2,
        ),
        start=12,
        end=168,
        fill=light,
        width=line,
    )
    _ellipse(
        draw,
        (x - half // 3, y - half // 4, x - half // 8, y),
        fill=_mix(main, shadow, 0.25),
    )
    _ellipse(
        draw,
        (x + half // 6, y + half // 8, x + half // 3, y + half // 3),
        fill=_mix(second, main, 0.35),
    )


def _draw_wave_motif(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    size: int,
    style: VisualStyle,
    line: int,
) -> None:
    """Рисует знак артиста в виде волны."""
    x, y = center
    half = size // 2
    main, second, shadow, light = _motif_colors(style)

    for index in range(3):
        yy = y - half // 3 + index * half // 3
        points = []
        for step in range(18):
            px = x - half + step * size // 17
            wave = math.sin(step / 17 * math.tau * 1.5 + index)
            points.append((px, int(yy + wave * half // 6)))
        draw.line(points, fill=(main, second, light)[index], width=line)

    _ellipse(
        draw,
        (x - half // 4, y - half, x + half // 4, y - half // 2),
        fill=main,
        outline=shadow,
        width=max(line // 3, 1),
    )


def _draw_artist_motif(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    size: int,
    style: VisualStyle,
    seed: str,
    badge: bool = False,
) -> None:
    """Рисует узнаваемый знак артиста: персонаж, растение, гора и т.п."""
    line = max(size // 16, 2)
    digest = _digest('artist-motif', _artist_seed(seed))
    motif_type = (style.motif_type + digest[0]) % 6

    if badge:
        _draw_motif_badge(draw, center, size, style, line)

    motif_drawers = (
        _draw_frontman_motif,
        _draw_plant_motif,
        _draw_mountain_motif,
        _draw_mascot_motif,
        _draw_planet_motif,
        _draw_wave_motif,
    )
    motif_drawers[motif_type](draw, center, size, style, line)


def _draw_album_panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    style: VisualStyle,
    seed: str,
) -> None:
    """Рисует мини-обложку с наследуемым знаком артиста."""
    left, top, right, bottom = box
    radius = max((right - left) // 20, 5)
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=_mix(style.background, style.primary, 0.20),
    )
    inner = (left + radius, top + radius, right - radius, bottom - radius)
    draw.rounded_rectangle(
        inner,
        radius=radius,
        fill=_mix(style.surface, style.background, 0.12),
    )
    _line_texture(draw, inner, style.primary, seed)
    _draw_music_icon(
        draw,
        (left + (right - left) * 3 // 4, top + (bottom - top) // 4),
        max((right - left) // 4, 12),
        style,
        seed,
    )
    _draw_artist_motif(
        draw,
        ((left + right) // 2, (top + bottom) // 2),
        max((right - left) * 2 // 5, 18),
        style,
        seed,
        badge=True,
    )


def _draw_artist_cover(
    size: int,
    style: VisualStyle,
    seed: str,
) -> Image.Image:
    img = _canvas(size, style, f'artist:{seed}')
    draw = ImageDraw.Draw(img)
    margin = size // 10

    # Артист — чистый знак/талисман без музыкальной абстракции и шума.
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=size // 9,
        fill=_mix(style.surface, style.background, 0.08),
        outline=_mix(style.dark, style.primary, 0.18),
        width=max(size // 90, 2),
    )
    _draw_artist_motif(
        draw,
        (size // 2, size // 2),
        size * 3 // 5,
        style,
        seed,
        badge=False,
    )
    return img


def _draw_album_cover(size: int, style: VisualStyle, seed: str) -> Image.Image:
    img = _canvas(size, style, f'album:{seed}')
    draw = ImageDraw.Draw(img)
    margin = size // 10
    digest = _digest('album-cover', seed)

    card = (margin, margin, size - margin, size - margin)
    draw.rounded_rectangle(
        card,
        radius=size // 18,
        fill=_mix(style.surface, style.background, 0.08),
        outline=_mix(style.dark, style.primary, 0.20),
        width=max(size // 90, 2),
    )
    _line_texture(draw, card, style.primary, f'album:{seed}')

    # Уникальность альбома — музыкальный знак и небольшие полосы.
    icon_center = (size * 2 // 3, size // 3)
    _draw_music_icon(draw, icon_center, size // 4, style, seed)
    stripe_y = size * 3 // 4
    stripe_count = 2 + digest[0] % 3
    for index in range(stripe_count):
        y = stripe_y + index * max(size // 28, 3)
        draw.rounded_rectangle(
            (margin * 2, y, size - margin * 2, y + max(size // 55, 2)),
            radius=max(size // 100, 1),
            fill=(style.primary, style.secondary, style.accent)[index % 3],
        )

    # Наследование артиста — уменьшенный рисунок в бейдже.
    _draw_artist_motif(
        draw,
        (size // 3, size // 2),
        size * 2 // 5,
        style,
        seed,
        badge=True,
    )
    return img


def _draw_vinyl(size: int, style: VisualStyle, seed: str) -> Image.Image:
    img = _canvas(size, style, f'vinyl:{seed}')
    draw = ImageDraw.Draw(img)
    margin = size // 10
    sleeve = (margin, margin, size - margin * 2, size - margin)
    disc_center = (size - margin * 2, size // 2)
    disc_radius = size // 3

    _ellipse(
        draw,
        (
            disc_center[0] - disc_radius,
            disc_center[1] - disc_radius,
            disc_center[0] + disc_radius,
            disc_center[1] + disc_radius,
        ),
        fill=_mix(style.dark, (0, 0, 0), 0.35),
    )
    for radius in range(disc_radius, disc_radius // 4, -max(size // 42, 8)):
        _ellipse(
            draw,
            (
                disc_center[0] - radius,
                disc_center[1] - radius,
                disc_center[0] + radius,
                disc_center[1] + radius,
            ),
            outline=_mix(style.surface, style.dark, 0.22),
            width=max(size // 180, 2),
        )
    label_radius = size // 9
    _ellipse(
        draw,
        (
            disc_center[0] - label_radius,
            disc_center[1] - label_radius,
            disc_center[0] + label_radius,
            disc_center[1] + label_radius,
        ),
        fill=style.accent,
    )
    _draw_artist_motif(draw, disc_center, size // 6, style, seed)
    _draw_album_panel(draw, sleeve, style, seed)
    return img


def _draw_cd(size: int, style: VisualStyle, seed: str) -> Image.Image:
    img = _canvas(size, style, f'cd:{seed}')
    draw = ImageDraw.Draw(img)
    center = (size // 2, size // 2)
    radius = size // 3
    draw.rounded_rectangle(
        (size // 7, size // 7, size - size // 7, size - size // 7),
        radius=size // 24,
        fill=_mix(style.surface, style.background, 0.24),
        outline=_mix(style.primary, style.dark, 0.25),
        width=max(size // 90, 3),
    )
    disc_box = (
        center[0] - radius,
        center[1] - radius,
        center[0] + radius,
        center[1] + radius,
    )
    _ellipse(
        draw,
        disc_box,
        fill=_mix(style.surface, (255, 255, 255), 0.16),
        outline=style.accent,
        width=max(size // 80, 3),
    )
    draw.pieslice(
        disc_box,
        start=20,
        end=82,
        fill=_mix(style.accent, (255, 255, 255), 0.12),
    )
    hole = size // 13
    _ellipse(
        draw,
        (
            center[0] - hole,
            center[1] - hole,
            center[0] + hole,
            center[1] + hole,
        ),
        fill=style.background,
        outline=style.dark,
        width=max(size // 120, 2),
    )
    _draw_artist_motif(
        draw,
        (center[0], center[1] + radius // 2),
        size // 5,
        style,
        seed,
        badge=True,
    )
    return img


def _draw_cassette(size: int, style: VisualStyle, seed: str) -> Image.Image:
    img = _canvas(size, style, f'cassette:{seed}')
    draw = ImageDraw.Draw(img)
    margin = size // 8
    body = (margin, size // 4, size - margin, size - size // 4)
    draw.rounded_rectangle(
        body,
        radius=size // 22,
        fill=_mix(style.surface, style.primary, 0.12),
        outline=style.dark,
        width=max(size // 80, 3),
    )
    label = (
        margin + size // 14,
        size // 3,
        size - margin - size // 14,
        size // 2,
    )
    draw.rounded_rectangle(label, radius=size // 44, fill=style.background)
    draw.rectangle(
        (
            label[0] + size // 24,
            label[1] + size // 24,
            label[2] - size // 24,
            label[1] + size // 18,
        ),
        fill=style.accent,
    )
    for x in (size // 3, size * 2 // 3):
        radius = size // 10
        _ellipse(
            draw,
            (x - radius, size // 2 - radius, x + radius, size // 2 + radius),
            fill=style.dark,
        )
        inner = radius // 2
        _ellipse(
            draw,
            (x - inner, size // 2 - inner, x + inner, size // 2 + inner),
            fill=style.surface,
        )
    draw.rounded_rectangle(
        (size // 3, size - size // 3, size * 2 // 3, size - size // 4),
        radius=size // 48,
        fill=style.dark,
    )
    _draw_artist_motif(
        draw,
        (size // 2, size // 3 + size // 18),
        size // 5,
        style,
        seed,
        badge=True,
    )
    return img


def _shirt_points(size: int, shirt_type: int) -> list[tuple[int, int]]:
    """Возвращает силуэт футболки с несколькими вариантами кроя."""
    if shirt_type == 0:
        return [
            (size // 3, size // 5),
            (size * 2 // 3, size // 5),
            (size * 5 // 6, size // 3),
            (size * 3 // 4, size // 2),
            (size * 2 // 3, size * 9 // 10),
            (size // 3, size * 9 // 10),
            (size // 4, size // 2),
            (size // 6, size // 3),
        ]
    if shirt_type == 1:
        return [
            (size // 3, size // 5),
            (size * 2 // 3, size // 5),
            (size * 9 // 10, size // 3),
            (size * 4 // 5, size * 9 // 20),
            (size * 7 // 10, size * 9 // 10),
            (size * 3 // 10, size * 9 // 10),
            (size // 5, size * 9 // 20),
            (size // 10, size // 3),
        ]
    if shirt_type == 2:
        return [
            (size // 3, size // 5),
            (size * 2 // 3, size // 5),
            (size * 4 // 5, size // 3),
            (size * 7 // 10, size * 4 // 5),
            (size * 13 // 20, size * 9 // 10),
            (size * 7 // 20, size * 9 // 10),
            (size * 3 // 10, size * 4 // 5),
            (size // 5, size // 3),
        ]
    return [
        (size // 3, size // 5),
        (size * 2 // 3, size // 5),
        (size * 19 // 24, size // 3),
        (size * 17 // 24, size * 4 // 9),
        (size * 17 // 24, size * 9 // 10),
        (size * 7 // 24, size * 9 // 10),
        (size * 7 // 24, size * 4 // 9),
        (size * 5 // 24, size // 3),
    ]


def _draw_tshirt_variant_details(
    draw: ImageDraw.ImageDraw,
    size: int,
    style: VisualStyle,
    base_color: RGB,
    digest: bytes,
) -> None:
    """Рисует заметные отличия между футболками одного артиста."""
    detail_type = digest[2] % 5
    accent = _mix(style.accent, base_color, 0.25)
    second = _mix(style.secondary, base_color, 0.18)
    line = max(size // 70, 2)

    if detail_type == 0:
        draw.rounded_rectangle(
            (size // 4, size * 3 // 5, size * 3 // 4, size * 13 // 20),
            radius=max(size // 80, 1),
            fill=accent,
        )
    elif detail_type == 1:
        for index in range(2):
            x = size // 4 + index * size // 2
            draw.line(
                (x, size // 4, x, size * 17 // 20),
                fill=(accent, second)[index],
                width=line,
            )
    elif detail_type == 2:
        draw.rounded_rectangle(
            (size * 11 // 20, size * 7 // 20, size * 7 // 10, size // 2),
            radius=max(size // 60, 2),
            fill=accent,
            outline=style.dark,
            width=max(size // 140, 1),
        )
    elif detail_type == 3:
        for index in range(3):
            y = size * 3 // 10 + index * size // 12
            draw.line(
                (size // 4, y, size * 3 // 4, y),
                fill=(accent, second, style.primary)[index],
                width=max(line // 2, 1),
            )
    else:
        draw.line(
            (size // 3, size * 9 // 10, size * 2 // 3, size // 5),
            fill=accent,
            width=line,
        )
        draw.line(
            (size * 2 // 3, size * 9 // 10, size // 3, size // 5),
            fill=second,
            width=max(line // 2, 1),
        )


def _draw_tshirt(size: int, style: VisualStyle, seed: str) -> Image.Image:
    img = _canvas(size, style, f'tshirt:{seed}')
    draw = ImageDraw.Draw(img)
    digest = _digest('tshirt', seed)
    shirt_type = (style.shirt_type + digest[0]) % 4
    shirt = _shirt_points(size, shirt_type)
    base_color = _mix(style.surface, style.primary, 0.08 + digest[1] / 1800)

    draw.polygon(shirt, fill=base_color)
    draw.line(shirt + [shirt[0]], fill=style.dark, width=max(size // 90, 3))
    collar = size // 13
    draw.arc(
        (
            size // 2 - collar,
            size // 5 - collar // 2,
            size // 2 + collar,
            size // 5 + collar,
        ),
        start=0,
        end=180,
        fill=style.dark,
        width=max(size // 90, 3),
    )
    if shirt_type in (1, 3):
        draw.line(
            (size // 3, size // 5, size // 4, size // 2),
            fill=_mix(style.accent, base_color, 0.35),
            width=max(size // 70, 2),
        )
        draw.line(
            (size * 2 // 3, size // 5, size * 3 // 4, size // 2),
            fill=_mix(style.accent, base_color, 0.35),
            width=max(size // 70, 2),
        )
    if shirt_type == 2:
        draw.rectangle(
            (
                size * 7 // 20,
                size * 4 // 5,
                size * 13 // 20,
                size * 9 // 10,
            ),
            fill=_mix(style.accent, base_color, 0.55),
        )

    _draw_tshirt_variant_details(draw, size, style, base_color, digest)
    _draw_artist_motif(
        draw,
        (size // 2, size // 2),
        size // 4,
        style,
        seed,
        badge=True,
    )
    return img


def _draw_cap_variant_details(
    draw: ImageDraw.ImageDraw,
    size: int,
    style: VisualStyle,
    cap_color: RGB,
    digest: bytes,
) -> None:
    """Рисует заметные отличия между кепками одного артиста."""
    detail_type = digest[1] % 5
    accent = _mix(style.accent, cap_color, 0.18)
    second = _mix(style.secondary, cap_color, 0.22)
    line = max(size // 75, 2)

    if detail_type == 0:
        draw.polygon(
            [
                (size // 5, size * 3 // 5),
                (size // 4, size * 7 // 20),
                (size * 2 // 5, size // 4),
                (size * 9 // 20, size * 3 // 5),
            ],
            fill=second,
        )
    elif detail_type == 1:
        draw.polygon(
            [
                (size * 11 // 20, size * 3 // 5),
                (size * 3 // 5, size // 4),
                (size * 3 // 4, size * 7 // 20),
                (size * 4 // 5, size * 3 // 5),
            ],
            fill=second,
        )
    elif detail_type == 2:
        for index in range(2):
            x = size * 2 // 5 + index * size // 5
            draw.line(
                (x, size // 4, x - size // 12, size * 3 // 5),
                fill=(accent, second)[index],
                width=line,
            )
    elif detail_type == 3:
        for index in range(3):
            y = size * 7 // 20 + index * size // 15
            draw.arc(
                (size // 4, y, size * 3 // 4, y + size // 4),
                start=205,
                end=335,
                fill=(accent, second, style.primary)[index],
                width=max(line // 2, 1),
            )
    else:
        draw.rounded_rectangle(
            (size * 7 // 20, size * 13 // 40, size * 13 // 20, size * 7 // 20),
            radius=max(size // 80, 1),
            fill=accent,
        )


def _draw_cap(size: int, style: VisualStyle, seed: str) -> Image.Image:
    img = _canvas(size, style, f'cap:{seed}')
    draw = ImageDraw.Draw(img)
    digest = _digest('cap', seed)
    cap_color = _mix(style.surface, style.primary, 0.18 + digest[0] / 1600)
    seam = _mix(style.dark, style.primary, 0.20)

    crown = [
        (size // 5, size * 3 // 5),
        (size // 4, size * 7 // 20),
        (size * 2 // 5, size // 4),
        (size * 3 // 5, size // 4),
        (size * 3 // 4, size * 7 // 20),
        (size * 4 // 5, size * 3 // 5),
    ]
    draw.polygon(crown, fill=cap_color)
    draw.line(crown + [crown[0]], fill=seam, width=max(size // 80, 3))
    draw.line(
        (size // 2, size // 4, size // 2, size * 3 // 5),
        fill=seam,
        width=max(size // 110, 2),
    )
    draw.arc(
        (size // 4, size // 4, size * 3 // 4, size * 4 // 5),
        start=200,
        end=340,
        fill=_mix(style.accent, cap_color, 0.35),
        width=max(size // 120, 2),
    )
    _ellipse(
        draw,
        (
            size // 2 - size // 28,
            size // 4 - size // 34,
            size // 2 + size // 28,
            size // 4 + size // 34,
        ),
        fill=style.accent,
    )
    _draw_cap_variant_details(draw, size, style, cap_color, digest)

    brim = [
        (size // 4, size * 3 // 5),
        (size * 3 // 4, size * 3 // 5),
        (size * 7 // 8, size * 7 // 10),
        (size * 3 // 5, size * 4 // 5),
        (size * 2 // 5, size * 4 // 5),
        (size // 8, size * 7 // 10),
    ]
    draw.polygon(brim, fill=style.accent)
    draw.line(brim + [brim[0]], fill=seam, width=max(size // 90, 3))
    draw.arc(
        (size // 5, size * 11 // 20, size * 4 // 5, size * 17 // 20),
        start=200,
        end=340,
        fill=_mix(style.surface, style.accent, 0.28),
        width=max(size // 120, 2),
    )

    _draw_artist_motif(
        draw,
        (size // 2, size // 9 * 4),
        size // 4,
        style,
        seed,
        badge=True,
    )
    return img


def _subject_image_kind(subject: str) -> str:
    """Определяет тип по subject без случайных substring-совпадений."""
    normalized = ''.join(char for char in subject.lower() if char.isalnum())

    if normalized in {'tshirt', 'tee', 'shirt', 'футболка'}:
        return 'tshirt'
    if normalized in {
        'cap',
        'hat',
        'baseballcap',
        'kepka',
        'кепка',
        'бейсболка',
    }:
        return 'cap'
    if normalized in {'cassette', 'audiocassette', 'tape', 'кассета'}:
        return 'cassette'
    if normalized in {'cd', 'disc', 'compactdisc', 'audiocd', 'диск'}:
        return 'cd'
    if normalized in {
        'vinyl',
        'vinylrecord',
        'record',
        'lp',
        'media',
        'носитель',
    }:
        return 'vinyl'
    if normalized in {'artist', 'артист'}:
        return 'artist'
    return 'album'


def generated_png_bytes(
    seed: str,
    subject: str,
    size: int = 128,
) -> bytes:
    """Генерирует связанную PNG-заглушку для артиста, альбома или товара."""
    style = _build_style(seed)
    kind = _subject_image_kind(subject)

    if kind == 'tshirt':
        img = _draw_tshirt(size, style, seed)
    elif kind == 'cap':
        img = _draw_cap(size, style, seed)
    elif kind == 'cassette':
        img = _draw_cassette(size, style, seed)
    elif kind == 'cd':
        img = _draw_cd(size, style, seed)
    elif kind == 'vinyl':
        img = _draw_vinyl(size, style, seed)
    elif kind == 'artist':
        img = _draw_artist_cover(size, style, seed)
    else:
        img = _draw_album_cover(size, style, seed)

    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def png_file_tuple(
    seed: str,
    subject: str,
    name: str,
) -> tuple[str, BytesIO, str]:
    """Возвращает file tuple для requests multipart-загрузки PNG."""
    return (
        name,
        BytesIO(generated_png_bytes(seed, subject)),
        'image/png',
    )
