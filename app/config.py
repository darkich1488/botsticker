from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class CategoryConfig:
    id: str
    title: str
    description: str
    path_to_templates: Path
    supports_recolor: bool


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    log_level: str
    base_dir: Path
    templates_root: Path
    temp_dir: Path
    previews_dir: Path
    price_per_template: float
    default_stroke_color: str
    default_elements_color: str
    preview_timeout_sec: int
    preview_fps: int
    preview_max_frames: int
    preview_max_gif_bytes: int
    random_pack_size: int
    templates_per_page: int
    lottie_renderer_cmd: str | None
    admin_user_ids: tuple[int, ...]
    payment_promo_codes: dict[str, float]
    payment_promo_max_uses: int
    categories: tuple[CategoryConfig, ...]


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_tuple_env(name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return default
    values: list[int] = []
    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        try:
            values.append(int(item))
        except ValueError:
            continue
    return tuple(dict.fromkeys(values)) if values else default


def _promo_codes_env(name: str) -> dict[str, float]:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return {}

    result: dict[str, float] = {}
    for chunk in raw.split(","):
        item = chunk.strip()
        if not item:
            continue
        if ":" in item:
            code_raw, amount_raw = item.split(":", 1)
        elif "=" in item:
            code_raw, amount_raw = item.split("=", 1)
        else:
            continue
        code = code_raw.strip().upper()
        if not code:
            continue
        try:
            amount = round(float(amount_raw.strip()), 2)
        except ValueError:
            continue
        if amount <= 0:
            continue
        result[code] = amount
    return result


def load_settings() -> Settings:
    load_dotenv()
    base_dir = Path(__file__).resolve().parents[1]

    templates_root = (base_dir / os.getenv("TEMPLATES_ROOT", "templates")).resolve()
    temp_dir = (base_dir / os.getenv("TEMP_DIR", "temp")).resolve()
    previews_dir = (base_dir / os.getenv("PREVIEWS_DIR", "previews")).resolve()

    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set")

    categories = (
        CategoryConfig(
            id="basic",
            title="Основной",
            description="Базовые шаблоны с текстом.",
            path_to_templates=(templates_root / "basic").resolve(),
            supports_recolor=False,
        ),
        CategoryConfig(
            id="recolor",
            title="Перекрас",
            description="Режим в разработке.",
            path_to_templates=(templates_root / "recolor").resolve(),
            supports_recolor=True,
        ),
    )

    renderer_cmd = (os.getenv("LOTTIE_RENDERER_CMD", "") or "").strip()

    return Settings(
        bot_token=bot_token,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        base_dir=base_dir,
        templates_root=templates_root,
        temp_dir=temp_dir,
        previews_dir=previews_dir,
        price_per_template=_float_env("PRICE_PER_TEMPLATE", 3.0),
        default_stroke_color=os.getenv("DEFAULT_STROKE_COLOR", "#111111"),
        default_elements_color=os.getenv("DEFAULT_ELEMENTS_COLOR", "#FFFFFF"),
        preview_timeout_sec=_int_env("PREVIEW_TIMEOUT_SEC", 20),
        preview_fps=_int_env("PREVIEW_FPS", 18),
        preview_max_frames=_int_env("PREVIEW_MAX_FRAMES", 48),
        preview_max_gif_bytes=_int_env("PREVIEW_MAX_GIF_BYTES", 3_500_000),
        random_pack_size=_int_env("RANDOM_PACK_SIZE", 6),
        templates_per_page=_int_env("TEMPLATES_PER_PAGE", 50),
        lottie_renderer_cmd=renderer_cmd or None,
        admin_user_ids=_int_tuple_env("ADMIN_USER_IDS", (925896498, 8619205109)),
        payment_promo_codes=_promo_codes_env("PAYMENT_PROMO_CODES"),
        payment_promo_max_uses=_int_env("PAYMENT_PROMO_MAX_USES", 100),
        categories=categories,
    )


def ensure_runtime_dirs(settings: Settings) -> None:
    settings.templates_root.mkdir(parents=True, exist_ok=True)
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    settings.previews_dir.mkdir(parents=True, exist_ok=True)
    for category in settings.categories:
        category.path_to_templates.mkdir(parents=True, exist_ok=True)
