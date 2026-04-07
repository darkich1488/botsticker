from __future__ import annotations

import copy
import gzip
import json
import logging
import os
import re
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any

from app.utils.files import read_json_file

DEFAULT_BG_MARKERS = ("фон", "bg", "background", "solid", "фигура 1")
DEFAULT_LOG_FILE = "bot_debug.log"
MAX_SKIPPED_NODES_LOG = 200
GLYPH_BANK_LAYER_NAME = "glyph_bank"
TARGET_TEXT_LAYER_NAME = "пример"
GENERATED_TEXT_SHAPE_LAYER_SUFFIX = "_shape"
DEBUG_GENERATED_SHAPE_LAYER = os.getenv("EMOJI_DEBUG_SHAPE_LAYER", "0").strip() not in {"0", "false", "False"}
GENERATED_LAYER_RENDER_ORDER = os.getenv("EMOJI_RENDER_ORDER", "last_to_first").strip().lower()
DEBUG_HIDE_OVERLAY_LAYERS = os.getenv("EMOJI_DEBUG_HIDE_OVERLAY_LAYERS", "0").strip() not in {"0", "false", "False"}
X_PLACEMENT_MODE = "local_paragraph_delta_relative_to_preserved_ks"
DEFAULT_TEXT_FONT_CANDIDATES = (
    "app/assets/fonts/Impact.ttf",
    "app/fonts/Impact.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/impact.ttf",
    "app/assets/fonts/NotoSans-Regular.ttf",
    "app/assets/fonts/DejaVuSans.ttf",
    "app/fonts/NotoSans-Regular.ttf",
    "app/fonts/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/local/share/fonts/NotoSans-Regular.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/Library/Fonts/Arial.ttf",
)

_TOKEN_BG_RE = re.compile(r"(?<![a-z0-9])bg(?![a-z0-9])", re.IGNORECASE)
_TOKEN_SOLID_RE = re.compile(r"(?<![a-z0-9])solid(?![a-z0-9])", re.IGNORECASE)
_TOKEN_FON_RE = re.compile(r"(?<![а-яёa-z0-9])фон(?![а-яёa-z0-9])", re.IGNORECASE)
_FIGURA1_RE = re.compile(r"(?<![а-яёa-z0-9])фигура\s*1(?![0-9а-яёa-z])", re.IGNORECASE)
_LAYER_PATH_RE = re.compile(r"^\$\.layers\[(\d+)\](?:\.|$)")
_RENDERABLE_LAYER_TYPES = {0, 1, 2, 4, 5}
_LAST_X_RENDER_MARKER: dict[str, Any] | None = None
_X_MARKER_TOKEN_KEY = "__emoji_x_marker_token__"
_X_RENDER_MARKER_BY_TOKEN: dict[str, dict[str, Any]] = {}
_X_RENDER_MARKER_LOCK = Lock()
_EMOJI2_TEMPLATE_FILE = "emoji2.json"
_EMOJI2_TEMPLATE_EXTRA_X_NUDGE = -24.65727
_EMOJI3_TEMPLATE_FILE = "emoji3.json"
_EMOJI4_TEMPLATE_FILE = "emoji4.json"
_EMOJI4_TEMPLATE_EXTRA_X_NUDGE = 62.0
_EMOJI4_FONT_SIZE_MULTIPLIER = 1.08
_EMOJI6_TEMPLATE_FILE = "emoji6.json"
_EMOJI6_FIXED_FONT_SIZE = 56.0
_EMOJI6_VISUAL_Y_NUDGE_PX = -22.0
_EMOJI8_TEMPLATE_FILE = "emoji7.json"
_EMOJI8_NESTED_TEXT_TEMPLATE_FILE = "emoji8.json"
_EMOJI8_NESTED_FIXED_FONT_SIZE = 32.4
_EMOJI8_NESTED_VISUAL_X_NUDGE_PX = -380.0
_EMOJI8_FIXED_FONT_SIZE = 64.0
_EMOJI8_VISUAL_X_NUDGE_PX = -12.0
_EMOJI8_VISUAL_Y_NUDGE_PX = -8.0
_EMOJI9_TEMPLATE_FILE = "emoji9.json"
_EMOJI9_VISUAL_X_NUDGE_PX = -20.0
_EMOJI9_TEXT_SIZE_DELTA_PX = 6.0
_EMOJI10_TEMPLATE_FILE = "emoji10.json"
_EMOJI10_VISUAL_X_NUDGE_PX = 60.0
_EMOJI10_TEXT_SIZE_MULTIPLIER = 3.0
_EMOJI10_TEXT_SIZE_DELTA_PX = 25.0
_EMOJI10_LONG_TEXT_SHRINK_BASE_PX = 6.0
_EMOJI10_LONG_TEXT_SHRINK_STEP_PX = 3.0
_EMOJI11_TEMPLATE_FILE = "emoji11.json"
_EMOJI11_VISUAL_X_NUDGE_PX = -190.0
_EMOJI11_VISUAL_Y_NUDGE_PX = -8.0
_EMOJI13_TEMPLATE_FILE = "emoji13.json"
_EMOJI13_FIXED_FONT_SIZE = 40.0
_EMOJI13_VISUAL_X_NUDGE_PX = 40.0
_EMOJI14_TEMPLATE_FILE = "emoji14.json"
_EMOJI14_FIXED_FONT_SIZE = 14.1
_EMOJI15_TEMPLATE_FILE = "emoji15.json"
_EMOJI15_FIXED_FONT_SIZE = 56.0
_EMOJI15_VISUAL_X_NUDGE_PX = -40.0
_EMOJI16_TEMPLATE_FILE = "emoji16.json"
_EMOJI16_FIXED_FONT_SIZE = 150.0
_EMOJI16_VISUAL_X_NUDGE_PX = 10.0
_EMOJI17_TEMPLATE_FILE = "emoji17.json"
_EMOJI17_FIXED_FONT_SIZE = 40.0
_EMOJI17_VISUAL_Y_NUDGE_PX = -20.0
_EMOJI18_TEMPLATE_FILE = "emoji18.json"
_EMOJI18_FIXED_FONT_SIZE = 150.0
_EMOJI18_VISUAL_X_NUDGE_PX = 120.0
_EMOJI19_TEMPLATE_FILE = "emoji19.json"
_EMOJI19_VISUAL_X_NUDGE_PX = 40.0
_EMOJI20_TEMPLATE_FILE = "emoji20.json"
_EMOJI20_FIXED_FONT_SIZE = 44.0
_EMOJI20_VISUAL_X_NUDGE_PX = -40.0
_EMOJI21_TEMPLATE_FILE = "emoji21.json"
_EMOJI21_VISUAL_X_NUDGE_PX = 40.0
_EMOJI22_TEMPLATE_FILE = "emoji22.json"
_EMOJI22_VISUAL_X_NUDGE_PX = -40.0
_EMOJI24_TEMPLATE_FILE = "emoji24.json"
_EMOJI24_VISUAL_X_NUDGE_PX = -80.0
_ZHOPBOL2_TEMPLATE_FILE = "жопболь2.json"
_ZHOPBOL2_VISUAL_Y_NUDGE_PX = -20.0
TELEGRAM_TGS_MAX_BYTES = 64 * 1024


def get_last_x_render_marker() -> dict[str, Any] | None:
    marker = _LAST_X_RENDER_MARKER
    if not isinstance(marker, dict):
        return None
    return copy.deepcopy(marker)


@dataclass(slots=True)
class BgDecision:
    is_bg: bool = False
    reason: str | None = None
    strong: bool = False


@dataclass(slots=True, frozen=True)
class TextBoxConfig:
    center_x: float
    center_y: float
    max_width: float
    max_height: float
    min_font_size: float
    base_font_size: float
    min_tracking: float = -12.0
    base_tracking: float = 0.0


BASIC_TEXT_BOX_CONFIG = TextBoxConfig(
    center_x=0.0,
    center_y=0.0,
    max_width=420.0,
    max_height=180.0,
    min_font_size=36.0,
    base_font_size=96.0,
    min_tracking=-16.0,
    base_tracking=0.0,
)


def _ensure_file_and_console_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_emoji_bot_logging_ready", False):
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    has_console = any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in root.handlers
    )
    if not has_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    has_file = any(
        isinstance(handler, logging.FileHandler)
        and Path(getattr(handler, "baseFilename", "")).name == DEFAULT_LOG_FILE
        for handler in root.handlers
    )
    if not has_file:
        file_handler = logging.FileHandler(DEFAULT_LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    setattr(root, "_emoji_bot_logging_ready", True)


@dataclass(slots=True)
class LottieProcessingStats:
    text_layers_found: int = 0
    text_keyframes_found: int = 0
    text_keyframes_updated: int = 0
    text_fill_colors_found: int = 0
    text_fill_colors_updated: int = 0
    text_stroke_colors_found: int = 0
    text_stroke_colors_updated: int = 0
    fill_nodes_found: int = 0
    stroke_nodes_found: int = 0
    fill_nodes_recolored: int = 0
    stroke_nodes_recolored: int = 0
    color_arrays_updated: int = 0
    skipped_color_nodes: int = 0
    text_layout_keyframes_logged: int = 0
    text_size_forced: int = 0
    text_visibility_warnings: int = 0
    skipped_nodes: list[str] = field(default_factory=list)

    @property
    def recolored_nodes_total(self) -> int:
        return self.fill_nodes_recolored + self.stroke_nodes_recolored


def hex_to_rgba(hex_color: str) -> list[float]:
    value = hex_color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) == 6:
        value = f"{value}FF"
    if len(value) != 8:
        raise ValueError(f"Invalid HEX color: {hex_color}")
    r = int(value[0:2], 16) / 255.0
    g = int(value[2:4], 16) / 255.0
    b = int(value[4:6], 16) / 255.0
    a = int(value[6:8], 16) / 255.0
    return [round(r, 6), round(g, 6), round(b, 6), round(a, 6)]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


def _looks_like_color_array(value: list[Any]) -> bool:
    if len(value) < 3:
        return False
    return all(_is_number(item) for item in value[:3])


def _set_color_array(target: list[Any], rgba: list[float]) -> bool:
    if not _looks_like_color_array(target):
        return False
    target[0] = rgba[0]
    target[1] = rgba[1]
    target[2] = rgba[2]
    if len(target) >= 4 and _is_number(target[3]):
        target[3] = rgba[3]
    return True


def _record_skipped(
    stats: LottieProcessingStats,
    logger: logging.Logger,
    path: str,
    reason: str,
) -> None:
    stats.skipped_color_nodes += 1
    if len(stats.skipped_nodes) < MAX_SKIPPED_NODES_LOG:
        stats.skipped_nodes.append(f"{path} ({reason})")
    logger.warning("Skipped color node path=%s reason=%s", path, reason)


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _is_glyph_bank_layer(layer_name: str) -> bool:
    return _normalize_name(layer_name) == _normalize_name(GLYPH_BANK_LAYER_NAME)


def _serialize_for_log(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return repr(value)


def _quantize_float_value(value: float, precision: int) -> float:
    rounded = round(value, precision)
    if rounded == 0:
        return 0.0
    return float(rounded)


def _shrink_lottie_payload(
    node: Any,
    *,
    float_precision: int | None = None,
    strip_metadata: bool = False,
    at_root: bool = True,
) -> Any:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            if strip_metadata:
                if key in {"mn", "ln", "cl"}:
                    continue
                if key == "nm" and not at_root:
                    continue
                if key in {"ix", "cix", "np"}:
                    continue
                if key == "markers" and at_root:
                    continue
                if key == "meta" and at_root:
                    continue
                if key == "hd" and value is False:
                    continue
                if key == "ao" and value == 0:
                    continue
                if key == "bm" and value == 0:
                    continue
                if key == "ddd" and (value == 0) and not at_root:
                    continue
                if key == "sr" and isinstance(value, (int, float)) and abs(float(value) - 1.0) < 1e-9:
                    continue
                if key == "st" and isinstance(value, (int, float)) and abs(float(value)) < 1e-9:
                    continue
            out[key] = _shrink_lottie_payload(
                value,
                float_precision=float_precision,
                strip_metadata=strip_metadata,
                at_root=False,
            )
        return out
    if isinstance(node, list):
        return [
            _shrink_lottie_payload(
                item,
                float_precision=float_precision,
                strip_metadata=strip_metadata,
                at_root=False,
            )
            for item in node
        ]
    if isinstance(node, float) and float_precision is not None:
        return _quantize_float_value(node, float_precision)
    return node


def _encode_tgs_payload(payload: dict[str, Any]) -> tuple[bytes, bytes]:
    compact_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = gzip.compress(compact_json, compresslevel=9)
    return compact_json, compressed


def _extract_animatable_value(prop: Any) -> Any:
    if not isinstance(prop, dict):
        return prop
    if "k" not in prop:
        return prop
    value = prop.get("k")
    if isinstance(value, list) and value and isinstance(value[0], dict):
        first_keyframe = value[0]
        if isinstance(first_keyframe.get("s"), list):
            return first_keyframe.get("s")
        if "k" in first_keyframe:
            return first_keyframe.get("k")
    return value


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _as_xy(value: Any) -> tuple[float, float] | None:
    if isinstance(value, list) and len(value) >= 2:
        x = _as_float(value[0])
        y = _as_float(value[1])
        if x is not None and y is not None:
            return x, y
    return None


def _as_xyz(value: Any) -> tuple[float, float, float] | None:
    if isinstance(value, list) and len(value) >= 2:
        x = _as_float(value[0])
        y = _as_float(value[1])
        if x is None or y is None:
            return None
        z = _as_float(value[2]) if len(value) >= 3 else 0.0
        if z is None:
            z = 0.0
        return x, y, z
    return None


def _set_xyz_on_vector(target: Any, new_xyz: list[float]) -> bool:
    if not isinstance(target, list) or len(target) < 2:
        return False
    changed = False
    for index in range(3):
        new_value = float(new_xyz[index])
        if index < len(target):
            old_value = _as_float(target[index])
            if old_value is None or abs(old_value - new_value) > 1e-9:
                target[index] = new_value
                changed = True
        else:
            target.append(new_value)
            changed = True
    return changed


def _apply_position_override(position_prop: Any, new_xyz: list[float]) -> tuple[bool, str]:
    if isinstance(position_prop, dict):
        key_data = position_prop.get("k")
        if isinstance(key_data, list):
            if key_data and isinstance(key_data[0], dict):
                changed = False
                for keyframe in key_data:
                    if not isinstance(keyframe, dict):
                        continue
                    if isinstance(keyframe.get("s"), list):
                        changed = _set_xyz_on_vector(keyframe["s"], new_xyz) or changed
                    if isinstance(keyframe.get("e"), list):
                        changed = _set_xyz_on_vector(keyframe["e"], new_xyz) or changed
                return changed, "keyframed_k"
            changed = _set_xyz_on_vector(key_data, new_xyz)
            return changed, "static_k"
        return False, "missing_or_invalid_k"
    if isinstance(position_prop, list):
        changed = _set_xyz_on_vector(position_prop, new_xyz)
        return changed, "raw_list"
    return False, "unsupported_structure"


def _default_text_box_for_layer(layer_name: str) -> TextBoxConfig | None:
    if _normalize_name(layer_name) == _normalize_name(TARGET_TEXT_LAYER_NAME):
        return BASIC_TEXT_BOX_CONFIG
    return None


def _text_len_for_fit(value: str) -> int:
    compact = "".join(ch for ch in value if not ch.isspace())
    return max(1, len(compact))


def _text_len_size_penalty_px(text_len: int) -> float:
    # Stronger global shrink by total symbol count.
    if text_len <= 4:
        return 0.0
    if text_len <= 6:
        return 3.0
    if text_len <= 8:
        return 5.0
    if text_len <= 10:
        return 7.0
    if text_len <= 12:
        return 9.0
    if text_len <= 15:
        return 11.0
    extra_steps = ((text_len - 16) // 3) + 1
    return float(11.0 + (extra_steps * 2.0))


def _heuristic_font_scale(text_len: int) -> float:
    if text_len <= 3:
        return 1.0
    if text_len <= 5:
        return 0.9
    if text_len <= 8:
        return 0.78
    return 0.62


def _estimate_text_width(text_len: int, font_size: float, tracking: float) -> float:
    return max(1, text_len) * max(0.0, (font_size * 0.56) + (tracking * 0.08))


def _compute_text_box_layout_values(
    *,
    new_text: str,
    text_box_config: TextBoxConfig,
    old_tracking: float | None,
) -> tuple[float, float, float, int, float]:
    text_len = _text_len_for_fit(new_text)
    text_len_penalty_px = _text_len_size_penalty_px(text_len)
    target_size = text_box_config.base_font_size * _heuristic_font_scale(text_len)
    target_size = target_size - text_len_penalty_px
    target_size = min(text_box_config.base_font_size, target_size)
    target_size = max(text_box_config.min_font_size, target_size)

    target_tracking = old_tracking if old_tracking is not None else text_box_config.base_tracking
    if text_len >= 6:
        target_tracking = min(target_tracking, -1.0)
    if text_len >= 9:
        target_tracking = min(target_tracking, -4.0)
    target_tracking = max(text_box_config.min_tracking, target_tracking)

    target_size = min(target_size, text_box_config.max_height * 0.92)
    estimated_width = _estimate_text_width(text_len, target_size, target_tracking)

    while estimated_width > text_box_config.max_width and target_size > text_box_config.min_font_size:
        target_size = max(text_box_config.min_font_size, target_size - 1.0)
        estimated_width = _estimate_text_width(text_len, target_size, target_tracking)

    while estimated_width > text_box_config.max_width and target_tracking > text_box_config.min_tracking:
        target_tracking = max(text_box_config.min_tracking, target_tracking - 0.5)
        estimated_width = _estimate_text_width(text_len, target_size, target_tracking)

    return (
        float(round(target_size, 3)),
        float(round(target_tracking, 3)),
        float(estimated_width),
        int(text_len),
        float(round(text_len_penalty_px, 3)),
    )


def _apply_text_box_layout(
    style: dict[str, Any],
    new_text: str,
    text_box_config: TextBoxConfig,
    path: str,
    logger: logging.Logger,
) -> tuple[float, float]:
    text_len = _text_len_for_fit(new_text)
    old_size = _as_float(style.get("s"))
    old_tracking = _as_float(style.get("tr"))
    target_size, target_tracking, estimated_width, _fit_text_len, text_len_penalty_px = _compute_text_box_layout_values(
        new_text=new_text,
        text_box_config=text_box_config,
        old_tracking=old_tracking,
    )

    style["s"] = round(target_size, 3)
    style["tr"] = round(target_tracking, 3)
    style["j"] = 2
    style["sz"] = [float(text_box_config.max_width), float(text_box_config.max_height)]
    style["ps"] = [float(text_box_config.center_x), float(text_box_config.center_y)]

    logger.info(
        (
            "Text auto-fit path=%s text_len=%s old_size=%s new_size=%s old_tr=%s new_tr=%s "
            "box_center=[%s,%s] box_size=[%s,%s] est_width=%s max_width=%s "
            "text_len_penalty_px=%s"
        ),
        path,
        text_len,
        old_size,
        style["s"],
        old_tracking,
        style["tr"],
        text_box_config.center_x,
        text_box_config.center_y,
        text_box_config.max_width,
        text_box_config.max_height,
        round(estimated_width, 2),
        text_box_config.max_width,
        text_len_penalty_px,
    )
    return float(style["s"]), float(style["tr"])


def _to_vec3(value: Any, default: list[float]) -> list[float]:
    if isinstance(value, list) and len(value) >= 2:
        x = _as_float(value[0])
        y = _as_float(value[1])
        z = _as_float(value[2]) if len(value) >= 3 else float(default[2])
        if x is not None and y is not None:
            return [float(x), float(y), float(z if z is not None else default[2])]
    return [float(default[0]), float(default[1]), float(default[2])]


def _to_scalar(value: Any, default: float) -> float:
    numeric = _as_float(value)
    return float(default if numeric is None else numeric)


def _lerp_values(start: Any, end: Any, alpha: float) -> Any:
    if isinstance(start, list) and isinstance(end, list):
        size = min(len(start), len(end))
        out: list[Any] = []
        for index in range(size):
            a = _as_float(start[index])
            b = _as_float(end[index])
            if a is None or b is None:
                out.append(start[index])
            else:
                out.append(a + (b - a) * alpha)
        return out
    a = _as_float(start)
    b = _as_float(end)
    if a is None or b is None:
        return start
    return a + (b - a) * alpha


def _extract_keyframed_times(prop: Any) -> set[float]:
    times: set[float] = set()
    if not isinstance(prop, dict):
        return times
    key_data = prop.get("k")
    if not (isinstance(key_data, list) and key_data and isinstance(key_data[0], dict)):
        return times
    for frame in key_data:
        if not isinstance(frame, dict):
            continue
        t = _as_float(frame.get("t"))
        if t is not None:
            times.add(float(t))
    return times


def _extract_position_keyframed_times(prop: Any) -> set[float]:
    if not isinstance(prop, dict):
        return set()
    if prop.get("s") in (1, True) and any(axis in prop for axis in ("x", "y", "z")):
        times: set[float] = set()
        for axis in ("x", "y", "z"):
            times.update(_extract_keyframed_times(prop.get(axis)))
        return times
    return _extract_keyframed_times(prop)


def _eval_anim_prop_at_t(prop: Any, t: float, default: Any) -> Any:
    if not isinstance(prop, dict):
        return default
    key_data = prop.get("k")
    if not isinstance(key_data, list):
        return key_data if key_data is not None else default
    if not key_data:
        return default
    if not isinstance(key_data[0], dict):
        return key_data

    frames = [frame for frame in key_data if isinstance(frame, dict)]
    if not frames:
        return default
    frames.sort(key=lambda frame: _to_scalar(frame.get("t"), 0.0))

    if len(frames) == 1:
        frame = frames[0]
        if "s" in frame:
            return copy.deepcopy(frame["s"])
        if "k" in frame:
            return copy.deepcopy(frame["k"])
        if "e" in frame:
            return copy.deepcopy(frame["e"])
        return default

    first_t = _to_scalar(frames[0].get("t"), 0.0)
    if t <= first_t:
        frame = frames[0]
        return copy.deepcopy(frame.get("s", frame.get("k", default)))

    for index in range(len(frames) - 1):
        current = frames[index]
        nxt = frames[index + 1]
        t0 = _to_scalar(current.get("t"), 0.0)
        t1 = _to_scalar(nxt.get("t"), t0)
        if t < t1:
            start_value = current.get("s", current.get("k", default))
            end_value = current.get("e", nxt.get("s", nxt.get("k", start_value)))
            if t1 <= t0:
                return copy.deepcopy(start_value)
            alpha = max(0.0, min(1.0, (t - t0) / (t1 - t0)))
            return _lerp_values(start_value, end_value, alpha)

    last = frames[-1]
    if "s" in last:
        return copy.deepcopy(last["s"])
    if "e" in last:
        return copy.deepcopy(last["e"])
    if "k" in last:
        return copy.deepcopy(last["k"])
    return default


def _eval_position_prop_at_t(prop: Any, t: float, default: list[float]) -> list[float]:
    if isinstance(prop, dict) and prop.get("s") in (1, True) and any(axis in prop for axis in ("x", "y", "z")):
        x_raw = _eval_anim_prop_at_t(prop.get("x"), t, default[0])
        y_raw = _eval_anim_prop_at_t(prop.get("y"), t, default[1])
        z_raw = _eval_anim_prop_at_t(prop.get("z"), t, default[2]) if "z" in prop else default[2]
        x = _to_scalar(x_raw, default[0])
        y = _to_scalar(y_raw, default[1])
        z = _to_scalar(z_raw, default[2])
        return [x, y, z]
    return _to_vec3(_eval_anim_prop_at_t(prop, t, default), default)


def _identity_matrix_2d() -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def _mat_mul_2d(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [
            (left[row][0] * right[0][col])
            + (left[row][1] * right[1][col])
            + (left[row][2] * right[2][col])
            for col in range(3)
        ]
        for row in range(3)
    ]


def _mat_translate_2d(x: float, y: float) -> list[list[float]]:
    return [
        [1.0, 0.0, x],
        [0.0, 1.0, y],
        [0.0, 0.0, 1.0],
    ]


def _mat_scale_2d(x: float, y: float) -> list[list[float]]:
    return [
        [x, 0.0, 0.0],
        [0.0, y, 0.0],
        [0.0, 0.0, 1.0],
    ]


def _mat_rotate_2d(radians: float) -> list[list[float]]:
    from math import cos, sin

    c = cos(radians)
    s = sin(radians)
    return [
        [c, -s, 0.0],
        [s, c, 0.0],
        [0.0, 0.0, 1.0],
    ]


def _mat_apply_to_point_2d(matrix: list[list[float]], x: float, y: float) -> tuple[float, float]:
    px = (matrix[0][0] * x) + (matrix[0][1] * y) + matrix[0][2]
    py = (matrix[1][0] * x) + (matrix[1][1] * y) + matrix[1][2]
    return px, py


def _collect_layer_chain(
    source_layer: dict[str, Any],
    layers_by_ind: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    visited: set[int] = set()
    current = source_layer
    while isinstance(current, dict):
        chain.append(current)
        current_ind = _as_int(current.get("ind"))
        if current_ind is not None:
            if current_ind in visited:
                break
            visited.add(current_ind)
        parent_id = _as_int(current.get("parent"))
        if parent_id in (None, 0):
            break
        current = layers_by_ind.get(parent_id)
        if current is None:
            break
    chain.reverse()
    return chain


def _build_chain_matrix_2d(
    source_layer: dict[str, Any],
    layers_by_ind: dict[int, dict[str, Any]],
    *,
    t: float = 0.0,
) -> tuple[list[list[float]], list[str]]:
    chain = _collect_layer_chain(source_layer, layers_by_ind)
    if not chain:
        return _identity_matrix_2d(), []
    matrix = _identity_matrix_2d()
    chain_debug: list[str] = []
    for layer in chain:
        p, a, s, r, _ = _eval_layer_transform(layer, t)
        matrix = _mat_mul_2d(matrix, _compose_layer_matrix(p, a, s, r))
        chain_debug.append(f"{layer.get('ind')}:{layer.get('nm')}")
    return matrix, chain_debug


def _project_local_point_to_comp_space(
    source_layer: dict[str, Any],
    layers_by_ind: dict[int, dict[str, Any]],
    point_xy: tuple[float, float],
    *,
    t: float = 0.0,
) -> tuple[tuple[float, float], list[str]]:
    matrix, chain_debug = _build_chain_matrix_2d(
        source_layer=source_layer,
        layers_by_ind=layers_by_ind,
        t=t,
    )
    return _mat_apply_to_point_2d(matrix, point_xy[0], point_xy[1]), chain_debug


def _project_comp_delta_to_local_delta(
    source_layer: dict[str, Any],
    layers_by_ind: dict[int, dict[str, Any]],
    *,
    comp_delta_xy: tuple[float, float],
    t: float = 0.0,
) -> tuple[tuple[float, float] | None, dict[str, Any]]:
    matrix, chain_debug = _build_chain_matrix_2d(
        source_layer=source_layer,
        layers_by_ind=layers_by_ind,
        t=t,
    )
    a = matrix[0][0]
    c = matrix[0][1]
    b = matrix[1][0]
    d = matrix[1][1]
    det = (a * d) - (b * c)
    debug: dict[str, Any] = {
        "linear": [[a, c], [b, d]],
        "det": det,
        "chain": chain_debug,
    }
    if abs(det) < 1e-9:
        return None, debug
    inv00 = d / det
    inv01 = -c / det
    inv10 = -b / det
    inv11 = a / det
    debug["inverse"] = [[inv00, inv01], [inv10, inv11]]
    comp_dx, comp_dy = comp_delta_xy
    local_dx = (inv00 * comp_dx) + (inv01 * comp_dy)
    local_dy = (inv10 * comp_dx) + (inv11 * comp_dy)
    return (local_dx, local_dy), debug


def _project_comp_delta_to_local_delta_numeric(
    source_layer: dict[str, Any],
    layers_by_ind: dict[int, dict[str, Any]],
    *,
    base_local_xy: tuple[float, float],
    comp_delta_xy: tuple[float, float],
    t: float = 0.0,
    eps: float = 1.0,
) -> tuple[tuple[float, float] | None, dict[str, Any]]:
    base_comp, chain_debug = _project_local_point_to_comp_space(
        source_layer=source_layer,
        layers_by_ind=layers_by_ind,
        point_xy=base_local_xy,
        t=t,
    )
    comp_x, _ = _project_local_point_to_comp_space(
        source_layer=source_layer,
        layers_by_ind=layers_by_ind,
        point_xy=(base_local_xy[0] + eps, base_local_xy[1]),
        t=t,
    )
    comp_y, _ = _project_local_point_to_comp_space(
        source_layer=source_layer,
        layers_by_ind=layers_by_ind,
        point_xy=(base_local_xy[0], base_local_xy[1] + eps),
        t=t,
    )
    j00 = (comp_x[0] - base_comp[0]) / eps
    j10 = (comp_x[1] - base_comp[1]) / eps
    j01 = (comp_y[0] - base_comp[0]) / eps
    j11 = (comp_y[1] - base_comp[1]) / eps
    det = (j00 * j11) - (j10 * j01)
    debug: dict[str, Any] = {
        "jacobian": [[j00, j01], [j10, j11]],
        "det": det,
        "chain": chain_debug,
        "eps": eps,
    }
    if abs(det) < 1e-9:
        return None, debug
    inv00 = j11 / det
    inv01 = -j01 / det
    inv10 = -j10 / det
    inv11 = j00 / det
    debug["inverse"] = [[inv00, inv01], [inv10, inv11]]
    comp_dx, comp_dy = comp_delta_xy
    local_dx = (inv00 * comp_dx) + (inv01 * comp_dy)
    local_dy = (inv10 * comp_dx) + (inv11 * comp_dy)
    return (local_dx, local_dy), debug


def _collect_chain_times(chain: list[dict[str, Any]]) -> list[float]:
    times: set[float] = {0.0}
    for layer in chain:
        ks = layer.get("ks")
        if not isinstance(ks, dict):
            continue
        times.update(_extract_position_keyframed_times(ks.get("p")))
        for key in ("a", "s", "r", "o"):
            times.update(_extract_keyframed_times(ks.get(key)))
    return sorted(times)


def _eval_layer_transform(
    layer: dict[str, Any],
    t: float,
) -> tuple[list[float], list[float], list[float], float, float]:
    ks = layer.get("ks") if isinstance(layer.get("ks"), dict) else {}
    p = _eval_position_prop_at_t(ks.get("p"), t, [0.0, 0.0, 0.0])
    a = _to_vec3(_eval_anim_prop_at_t(ks.get("a"), t, [0.0, 0.0, 0.0]), [0.0, 0.0, 0.0])
    s = _to_vec3(_eval_anim_prop_at_t(ks.get("s"), t, [100.0, 100.0, 100.0]), [100.0, 100.0, 100.0])
    r = _to_scalar(_eval_anim_prop_at_t(ks.get("r"), t, 0.0), 0.0)
    o = _to_scalar(_eval_anim_prop_at_t(ks.get("o"), t, 100.0), 100.0)
    return p, a, s, r, o


def _compose_layer_matrix(p: list[float], a: list[float], s: list[float], r_deg: float) -> list[list[float]]:
    from math import radians

    sx = s[0] / 100.0
    sy = s[1] / 100.0
    matrix = _mat_translate_2d(p[0], p[1])
    matrix = _mat_mul_2d(matrix, _mat_rotate_2d(radians(r_deg)))
    matrix = _mat_mul_2d(matrix, _mat_scale_2d(sx, sy))
    matrix = _mat_mul_2d(matrix, _mat_translate_2d(-a[0], -a[1]))
    return matrix


def _decompose_matrix(matrix: list[list[float]]) -> tuple[list[float], list[float], float]:
    from math import atan2, degrees, sqrt

    a = matrix[0][0]
    c = matrix[0][1]
    tx = matrix[0][2]
    b = matrix[1][0]
    d = matrix[1][1]
    ty = matrix[1][2]
    scale_x = sqrt((a * a) + (b * b)) * 100.0
    scale_y = sqrt((c * c) + (d * d)) * 100.0
    rotation = degrees(atan2(b, a))
    return [tx, ty, 0.0], [scale_x, scale_y, 100.0], rotation


def _build_linear_keyframes(values: list[tuple[float, Any]]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    if not values:
        return frames
    if len(values) == 1:
        t, value = values[0]
        frames.append({"t": t, "s": copy.deepcopy(value)})
        return frames
    for index in range(len(values)):
        t, value = values[index]
        frame: dict[str, Any] = {"t": t, "s": copy.deepcopy(value)}
        if index < len(values) - 1:
            frame["e"] = copy.deepcopy(values[index + 1][1])
        frames.append(frame)
    return frames


def _bake_layer_chain_transform(
    source_layer: dict[str, Any],
    layers_by_ind: dict[int, dict[str, Any]],
    *,
    source_position_offset: tuple[float, float] = (0.0, 0.0),
) -> tuple[dict[str, Any], dict[str, Any]]:
    # Bake is intentionally disabled: keep Telegram-valid behavior with preserve_parent_and_layer_ks.
    # This helper returns source ks unchanged (with minimal defaults), so legacy call sites
    # cannot accidentally re-enable world-transform baking.
    chain = _collect_layer_chain(source_layer, layers_by_ind)
    if not chain:
        chain = [source_layer]
    source_ks = source_layer.get("ks") if isinstance(source_layer.get("ks"), dict) else {}
    preserved_ks = copy.deepcopy(source_ks)
    preserved_ks.setdefault("o", {"a": 0, "k": 100})
    preserved_ks.setdefault("p", {"a": 0, "k": [0.0, 0.0, 0.0]})
    preserved_ks.setdefault("a", {"a": 0, "k": [0.0, 0.0, 0.0]})
    preserved_ks.setdefault("s", {"a": 0, "k": [100.0, 100.0, 100.0]})
    preserved_ks.setdefault("r", {"a": 0, "k": 0.0})
    preserved_ks.setdefault("sk", {"a": 0, "k": 0})
    preserved_ks.setdefault("sa", {"a": 0, "k": 0})
    debug = {
        "chain": [
            {
                "ind": layer.get("ind"),
                "nm": layer.get("nm"),
                "parent": layer.get("parent"),
            }
            for layer in chain
        ],
        "times": _collect_chain_times(chain),
        "final_p": _extract_animatable_value(preserved_ks.get("p")),
        "final_s": _extract_animatable_value(preserved_ks.get("s")),
        "final_r": _extract_animatable_value(preserved_ks.get("r")),
        "bake_disabled": True,
        "source_position_offset_ignored": [float(source_position_offset[0]), float(source_position_offset[1])],
    }
    return preserved_ks, debug


def _extract_rgba_from_lottie_value(value: Any) -> list[float] | None:
    if isinstance(value, list):
        if _looks_like_color_array(value):
            rgba = [float(value[0]), float(value[1]), float(value[2]), 1.0]
            if len(value) >= 4 and _is_number(value[3]):
                rgba[3] = float(value[3])
            return rgba
        for item in value:
            nested = _extract_rgba_from_lottie_value(item)
            if nested is not None:
                return nested
        return None

    if isinstance(value, dict):
        for key in ("k", "s", "e"):
            if key in value:
                nested = _extract_rgba_from_lottie_value(value[key])
                if nested is not None:
                    return nested
        for nested_value in value.values():
            if isinstance(nested_value, (dict, list)):
                nested = _extract_rgba_from_lottie_value(nested_value)
                if nested is not None:
                    return nested
        return None

    return None


def _resolve_fixed_text_font_path(logger: logging.Logger) -> Path:
    candidates: list[Path] = []
    env_font_path = os.getenv("EMOJI_TEXT_FONT_PATH", "").strip()
    if env_font_path:
        env_candidate = Path(env_font_path).expanduser()
        candidates.append(env_candidate)
        if not env_candidate.exists():
            logger.warning(
                "EMOJI_TEXT_FONT_PATH does not exist path=%s",
                str(env_candidate),
            )

    project_root = Path(__file__).resolve().parents[2]
    for candidate in DEFAULT_TEXT_FONT_CANDIDATES:
        path_candidate = Path(candidate).expanduser()
        if not path_candidate.is_absolute():
            path_candidate = (project_root / path_candidate).resolve()
        candidates.append(path_candidate)

    # Railway/base images can have fonts in non-standard paths; ask fontconfig when available.
    try:
        proc = subprocess.run(
            ["fc-list", ":", "file"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
        if proc.returncode == 0 and proc.stdout:
            for raw_line in proc.stdout.splitlines():
                path_part = raw_line.split(":", 1)[0].strip()
                if not path_part:
                    continue
                lowered = path_part.lower()
                if lowered.endswith((".ttf", ".otf", ".ttc")):
                    candidates.append(Path(path_part))
    except Exception:
        pass

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists() and candidate.is_file():
            logger.info("Text shape font selected path=%s", str(candidate))
            return candidate

    logger.error(
        "Text shape font selection failed checked_candidates=%s env_font_path_set=%s",
        len(seen),
        bool(env_font_path),
    )
    raise FileNotFoundError(
        "No suitable fixed font found for shape-text pipeline. "
        "Set EMOJI_TEXT_FONT_PATH or provide one of DEFAULT_TEXT_FONT_CANDIDATES."
    )


def _paths_bounds(paths: list[dict[str, Any]]) -> tuple[float, float, float, float] | None:
    min_x: float | None = None
    min_y: float | None = None
    max_x: float | None = None
    max_y: float | None = None

    for path in paths:
        vertices = path.get("v")
        if not isinstance(vertices, list):
            continue
        for point in vertices:
            if not isinstance(point, list) or len(point) < 2:
                continue
            x = _as_float(point[0])
            y = _as_float(point[1])
            if x is None or y is None:
                continue
            min_x = x if min_x is None else min(min_x, x)
            min_y = y if min_y is None else min(min_y, y)
            max_x = x if max_x is None else max(max_x, x)
            max_y = y if max_y is None else max(max_y, y)

    if min_x is None or min_y is None or max_x is None or max_y is None:
        return None
    return min_x, min_y, max_x, max_y


def _transform_paths(
    paths: list[dict[str, Any]],
    *,
    scale_factor: float,
    center_x: float,
    center_y: float,
    shift_x: float,
    shift_y: float,
) -> None:
    for path in paths:
        vertices = path.get("v")
        in_tangents = path.get("i")
        out_tangents = path.get("o")
        if not isinstance(vertices, list):
            continue

        for index, point in enumerate(vertices):
            if not isinstance(point, list) or len(point) < 2:
                continue
            x = _as_float(point[0])
            y = _as_float(point[1])
            if x is None or y is None:
                continue
            point[0] = center_x + (x - center_x) * scale_factor + shift_x
            point[1] = center_y + (y - center_y) * scale_factor + shift_y

            if isinstance(in_tangents, list) and index < len(in_tangents):
                tangent = in_tangents[index]
                if isinstance(tangent, list) and len(tangent) >= 2:
                    tx = _as_float(tangent[0])
                    ty = _as_float(tangent[1])
                    if tx is not None and ty is not None:
                        tangent[0] = tx * scale_factor
                        tangent[1] = ty * scale_factor

            if isinstance(out_tangents, list) and index < len(out_tangents):
                tangent = out_tangents[index]
                if isinstance(tangent, list) and len(tangent) >= 2:
                    tx = _as_float(tangent[0])
                    ty = _as_float(tangent[1])
                    if tx is not None and ty is not None:
                        tangent[0] = tx * scale_factor
                        tangent[1] = ty * scale_factor


def _build_text_shape_paths(
    text: str,
    *,
    font_path: Path,
    font_size: float,
    tracking: float,
    box_center_x: float,
    box_center_y: float,
    box_max_width: float,
    box_max_height: float,
    disable_fit_down: bool = False,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    try:
        from fontTools.pens.basePen import BasePen
        from fontTools.ttLib import TTFont
    except Exception as exc:
        raise RuntimeError(
            "fonttools is required for shape-text rendering. Install dependency: fonttools>=4.53.0"
        ) from exc

    class _GlyphToCubicPen(BasePen):
        def __init__(self, glyph_set: Any) -> None:
            super().__init__(glyph_set)
            self.contours: list[
                list[
                    tuple[
                        tuple[float, float],
                        tuple[float, float],
                        tuple[float, float],
                        tuple[float, float],
                    ]
                ]
            ] = []
            self._segments: list[
                tuple[
                    tuple[float, float],
                    tuple[float, float],
                    tuple[float, float],
                    tuple[float, float],
                ]
            ] = []
            self._start: tuple[float, float] | None = None
            self._current: tuple[float, float] | None = None

        def _moveTo(self, p0: tuple[float, float]) -> None:
            self._segments = []
            self._start = (float(p0[0]), float(p0[1]))
            self._current = self._start

        def _lineTo(self, p1: tuple[float, float]) -> None:
            if self._current is None:
                return
            end = (float(p1[0]), float(p1[1]))
            p0 = self._current
            c1 = (p0[0] + (end[0] - p0[0]) / 3.0, p0[1] + (end[1] - p0[1]) / 3.0)
            c2 = (p0[0] + 2.0 * (end[0] - p0[0]) / 3.0, p0[1] + 2.0 * (end[1] - p0[1]) / 3.0)
            self._segments.append((p0, c1, c2, end))
            self._current = end

        def _curveToOne(
            self,
            p1: tuple[float, float],
            p2: tuple[float, float],
            p3: tuple[float, float],
        ) -> None:
            if self._current is None:
                return
            p0 = self._current
            c1 = (float(p1[0]), float(p1[1]))
            c2 = (float(p2[0]), float(p2[1]))
            end = (float(p3[0]), float(p3[1]))
            self._segments.append((p0, c1, c2, end))
            self._current = end

        def _qCurveToOne(self, p1: tuple[float, float], p2: tuple[float, float]) -> None:
            if self._current is None:
                return
            p0 = self._current
            q = (float(p1[0]), float(p1[1]))
            end = (float(p2[0]), float(p2[1]))
            c1 = (p0[0] + (2.0 / 3.0) * (q[0] - p0[0]), p0[1] + (2.0 / 3.0) * (q[1] - p0[1]))
            c2 = (end[0] + (2.0 / 3.0) * (q[0] - end[0]), end[1] + (2.0 / 3.0) * (q[1] - end[1]))
            self._segments.append((p0, c1, c2, end))
            self._current = end

        def _closePath(self) -> None:
            if self._start is None or self._current is None:
                return
            if abs(self._current[0] - self._start[0]) > 1e-9 or abs(self._current[1] - self._start[1]) > 1e-9:
                self._lineTo(self._start)
            if self._segments:
                self.contours.append(self._segments)
            self._segments = []
            self._start = None
            self._current = None

        def _endPath(self) -> None:
            self._closePath()

    font = TTFont(str(font_path))
    try:
        glyph_set = font.getGlyphSet()
        cmap = font.getBestCmap() or {}
        hmtx = font["hmtx"].metrics
        units_per_em = float(font["head"].unitsPerEm)
        scale = float(font_size) / max(1.0, units_per_em)
        tracking_px = float(font_size) * (float(tracking) / 1000.0)

        if not text:
            return []

        space_advance_units = float(hmtx.get("space", (int(units_per_em * 0.5), 0))[0])
        question_glyph = cmap.get(ord("?"))
        fallback_glyph = question_glyph or ".notdef"

        paths: list[dict[str, Any]] = []
        cursor_x = 0.0
        for char in text:
            if char.isspace():
                cursor_x += (space_advance_units * scale) + tracking_px
                continue

            glyph_name = cmap.get(ord(char))
            if glyph_name is None:
                glyph_name = fallback_glyph
                logger.warning(
                    "Shape text missing glyph char=%r fallback=%s font=%s",
                    char,
                    glyph_name,
                    str(font_path),
                )

            if glyph_name not in glyph_set:
                logger.warning(
                    "Shape text glyph not found in glyphSet char=%r glyph=%s",
                    char,
                    glyph_name,
                )
                cursor_x += (space_advance_units * scale) + tracking_px
                continue

            glyph = glyph_set[glyph_name]
            pen = _GlyphToCubicPen(glyph_set)
            glyph.draw(pen)
            contours = pen.contours

            for contour_index, contour in enumerate(contours):
                if not contour:
                    continue
                vertices: list[list[float]] = []
                in_tangents: list[list[float]] = []
                out_tangents: list[list[float]] = []

                for segment in contour:
                    p0, c1, _, _ = segment
                    vertices.append([cursor_x + (p0[0] * scale), -(p0[1] * scale)])
                    out_tangents.append([
                        (c1[0] - p0[0]) * scale,
                        -((c1[1] - p0[1]) * scale),
                    ])
                    in_tangents.append([0.0, 0.0])

                for segment_index, segment in enumerate(contour):
                    _, _, c2, p1 = segment
                    next_index = (segment_index + 1) % len(contour)
                    next_anchor_x = cursor_x + (p1[0] * scale)
                    next_anchor_y = -(p1[1] * scale)
                    in_tangents[next_index] = [
                        (c2[0] * scale + cursor_x) - next_anchor_x,
                        (-(c2[1] * scale)) - next_anchor_y,
                    ]

                paths.append(
                    {
                        "i": in_tangents,
                        "o": out_tangents,
                        "v": vertices,
                        "c": True,
                    }
                )

            advance_units = float(hmtx.get(glyph_name, (int(units_per_em * 0.5), 0))[0])
            cursor_x += (advance_units * scale) + tracking_px

        bounds = _paths_bounds(paths)
        if bounds is None:
            return []

        min_x, min_y, max_x, max_y = bounds
        width = max_x - min_x
        height = max_y - min_y

        scale_factor = 1.0
        if width > 1e-6 and width > box_max_width:
            scale_factor = min(scale_factor, box_max_width / width)
        if height > 1e-6 and height > box_max_height:
            scale_factor = min(scale_factor, box_max_height / height)
        shape_fit_scale_before = scale_factor
        shape_fit_scale_after = 1.0 if disable_fit_down else scale_factor

        _transform_paths(
            paths,
            scale_factor=shape_fit_scale_after,
            center_x=0.0,
            center_y=0.0,
            shift_x=0.0,
            shift_y=0.0,
        )
        raw_local_bounds = _paths_bounds(paths)
        raw_min_x = raw_min_y = raw_max_x = raw_max_y = 0.0
        raw_center_x = 0.0
        if raw_local_bounds is not None:
            raw_min_x, raw_min_y, raw_max_x, raw_max_y = raw_local_bounds
            raw_center_x = (raw_min_x + raw_max_x) / 2.0
            if abs(raw_center_x) > 1e-6:
                _transform_paths(
                    paths,
                    scale_factor=1.0,
                    center_x=0.0,
                    center_y=0.0,
                    shift_x=-raw_center_x,
                    shift_y=0.0,
                )
        normalized_local_bounds = _paths_bounds(paths)
        norm_min_x = norm_min_y = norm_max_x = norm_max_y = 0.0
        norm_center_x = 0.0
        if normalized_local_bounds is not None:
            norm_min_x, norm_min_y, norm_max_x, norm_max_y = normalized_local_bounds
            norm_center_x = (norm_min_x + norm_max_x) / 2.0
        logger.info(
            (
                "Shape text paths built text=%r glyph_paths=%s font=%s "
                "font_size=%s tracking=%s width=%s height=%s scale=%s "
                "shape_fit_scale_before=%s shape_fit_scale_after=%s "
                "raw_bounds=[%s,%s,%s,%s] normalized_bounds=[%s,%s,%s,%s] center_x_after_normalization=%s "
                "target_center=[%s,%s] target_center_baked_into_paths=%s target_box=[%s,%s]"
            ),
            text,
            len(paths),
            str(font_path),
            round(font_size, 3),
            round(tracking, 3),
            round(width, 3),
            round(height, 3),
            round(shape_fit_scale_after, 4),
            round(shape_fit_scale_before, 4),
            round(shape_fit_scale_after, 4),
            round(raw_min_x, 3),
            round(raw_min_y, 3),
            round(raw_max_x, 3),
            round(raw_max_y, 3),
            round(norm_min_x, 3),
            round(norm_min_y, 3),
            round(norm_max_x, 3),
            round(norm_max_y, 3),
            round(norm_center_x, 6),
            box_center_x,
            box_center_y,
            False,
            box_max_width,
            box_max_height,
        )
        return paths
    finally:
        font.close()


def inject_text_shapes(
    data: dict[str, Any],
    layer_name: str = TARGET_TEXT_LAYER_NAME,
    template_name: str | None = None,
    logger: logging.Logger | None = None,
) -> int:
    global _LAST_X_RENDER_MARKER
    active_logger = logger or logging.getLogger(__name__)
    x_mode = X_PLACEMENT_MODE
    if x_mode not in {"local_paragraph_delta_only", "local_paragraph_delta_relative_to_preserved_ks"}:
        active_logger.warning(
            "Unknown x_mode=%s fallback=local_paragraph_delta_relative_to_preserved_ks",
            x_mode,
        )
        x_mode = "local_paragraph_delta_relative_to_preserved_ks"
    layers = data.get("layers")
    if not isinstance(layers, list):
        active_logger.warning("Text shape injection skipped reason=no_layers_array")
        return 0
    template_name_value = (template_name or str(data.get("__template_name__", ""))).strip()
    is_emoji4_template = template_name_value.lower() == _EMOJI4_TEMPLATE_FILE
    is_emoji10_template = template_name_value.lower() == _EMOJI10_TEMPLATE_FILE

    layers_by_ind: dict[int, dict[str, Any]] = {}
    for candidate in layers:
        if not isinstance(candidate, dict):
            continue
        ind = _as_int(candidate.get("ind"))
        if ind is None:
            continue
        layers_by_ind[ind] = candidate

    target_name = _normalize_name(layer_name)
    font_path = _resolve_fixed_text_font_path(active_logger)
    converted = 0

    for index, layer in enumerate(list(layers)):
        if not isinstance(layer, dict):
            continue
        if layer.get("ty") != 5:
            continue
        name_raw = str(layer.get("nm", "")).strip()
        if _is_glyph_bank_layer(name_raw):
            continue
        if _normalize_name(name_raw) != target_name:
            continue

        text_container = layer.get("t")
        if not isinstance(text_container, dict):
            active_logger.warning("Text shape injection skipped layer=%s reason=no_t_container", name_raw)
            continue
        keyframes = text_container.get("d", {}).get("k")
        if not isinstance(keyframes, list) or not keyframes:
            active_logger.warning("Text shape injection skipped layer=%s reason=no_text_keyframes", name_raw)
            continue

        style: dict[str, Any] | None = None
        for keyframe in keyframes:
            if not isinstance(keyframe, dict):
                continue
            candidate = keyframe.get("s")
            if isinstance(candidate, dict) and "t" in candidate:
                style = candidate
                break
        if style is None:
            active_logger.warning("Text shape injection skipped layer=%s reason=no_style_with_text", name_raw)
            continue

        text_value = str(style.get("t", ""))
        if not text_value.strip():
            active_logger.warning("Text shape injection skipped layer=%s reason=empty_text", name_raw)
            continue

        default_box = _default_text_box_for_layer(name_raw) or BASIC_TEXT_BOX_CONFIG
        raw_style_ps = style.get("ps")
        raw_style_sz = style.get("sz")
        style_ps = _as_xy(raw_style_ps)
        if style_ps is None:
            style_ps = _as_xy(_extract_animatable_value(raw_style_ps))
        style_sz = _as_xy(raw_style_sz)
        if style_sz is None:
            style_sz = _as_xy(_extract_animatable_value(raw_style_sz))
        justification = _as_int(style.get("j"))
        if justification is None:
            justification = 2
        source_local_ks = layer.get("ks") if isinstance(layer.get("ks"), dict) else {}
        source_local_p3 = _eval_position_prop_at_t(source_local_ks.get("p"), 0.0, [0.0, 0.0, 0.0])
        source_local_p = (float(source_local_p3[0]), float(source_local_p3[1]))
        source_local_a3 = _to_vec3(_extract_animatable_value(source_local_ks.get("a")), [0.0, 0.0, 0.0])
        source_local_s3 = _to_vec3(_extract_animatable_value(source_local_ks.get("s")), [100.0, 100.0, 100.0])
        has_parent_chain = _as_int(layer.get("parent")) not in (None, 0)
        source_ks_p_ignored_for_local_centering = has_parent_chain and source_local_p is not None
        if style_ps is not None and style_sz is not None:
            paragraph_box_center_x = style_ps[0] + (style_sz[0] / 2.0)
            paragraph_box_center_y = style_ps[1] + (style_sz[1] / 2.0)
            if justification == 2:
                box_center_x = paragraph_box_center_x
            elif justification == 1:
                box_center_x = style_ps[0] + style_sz[0]
            else:
                box_center_x = style_ps[0]
            rejected_vertical_center = paragraph_box_center_y
            box_center_y = style_ps[1]
            center_reason = "paragraph_x_align_baseline_y"
            active_logger.info(
                (
                    "Paragraph target center layer=%s ps=%s sz=%s j=%s "
                    "chosen_target_x=%s chosen_target_y=%s "
                    "paragraph_box_target_center=[%s,%s] rejected_vertical_center=%s "
                    "reason=vertical_center_not_used_for_paragraph_text"
                ),
                name_raw,
                _serialize_for_log(style_ps),
                _serialize_for_log(style_sz),
                justification,
                box_center_x,
                box_center_y,
                paragraph_box_center_x,
                paragraph_box_center_y,
                rejected_vertical_center,
            )
        else:
            box_center_x = default_box.center_x
            box_center_y = default_box.center_y
            center_reason = "default_text_box_center_no_paragraph_box"
        box_max_width = max(1.0, style_sz[0]) if style_sz else default_box.max_width
        box_max_height = max(1.0, style_sz[1]) if style_sz else default_box.max_height
        font_size = _as_float(style.get("s")) or default_box.base_font_size
        tracking = _as_float(style.get("tr")) or default_box.base_tracking
        line_height = _as_float(style.get("lh"))
        line_spacing = _as_float(style.get("ls"))
        active_logger.info(
            (
                "Shape text layout center selected layer=%s reason=%s target_center=[%s,%s] "
                "paragraph_ps=%s paragraph_sz=%s justification=%s source_local_p=%s "
                "has_parent_chain=%s source_ks_p_ignored_for_local_centering=%s lh=%s ls=%s tr=%s"
            ),
            name_raw,
            center_reason,
            box_center_x,
            box_center_y,
            _serialize_for_log(style_ps),
            _serialize_for_log(style_sz),
            justification,
            _serialize_for_log(source_local_p),
            has_parent_chain,
            source_ks_p_ignored_for_local_centering,
            line_height,
            line_spacing,
            tracking,
        )

        fill_rgba = _extract_rgba_from_lottie_value(style.get("fc")) or [1.0, 1.0, 1.0, 1.0]
        stroke_rgba = _extract_rgba_from_lottie_value(style.get("sc"))
        stroke_width = _as_float(style.get("sw")) or 0.0
        if stroke_rgba is not None and stroke_width <= 0.0:
            stroke_width = max(1.0, font_size * 0.03)

        paths = _build_text_shape_paths(
            text_value,
            font_path=font_path,
            font_size=font_size,
            tracking=tracking,
            box_center_x=0.0,
            box_center_y=0.0,
            box_max_width=box_max_width,
            box_max_height=box_max_height,
            disable_fit_down=(is_emoji4_template or is_emoji10_template),
            logger=active_logger,
        )
        active_logger.info(
            "Shape path build mode layer=%s absolute_target_center_baked_into_paths=%s",
            name_raw,
            False,
        )
        if not paths:
            active_logger.warning(
                "Text shape injection skipped layer=%s reason=empty_generated_paths text=%r",
                name_raw,
                text_value,
            )
            continue

        raw_bounds = _paths_bounds(paths)
        if raw_bounds is None:
            active_logger.warning(
                "Text shape injection skipped layer=%s reason=failed_raw_local_bounds text=%r",
                name_raw,
                text_value,
            )
            continue
        raw_min_x, raw_min_y, raw_max_x, raw_max_y = raw_bounds
        raw_center_x = (raw_min_x + raw_max_x) / 2.0
        raw_center_y = (raw_min_y + raw_max_y) / 2.0
        active_logger.info(
            (
                "Generated text raw local bounds right_after_path_build layer=%s "
                "min_x=%s min_y=%s max_x=%s max_y=%s center_x=%s center_y=%s"
            ),
            name_raw,
            round(raw_min_x, 3),
            round(raw_min_y, 3),
            round(raw_max_x, 3),
            round(raw_max_y, 3),
            round(raw_center_x, 3),
            round(raw_center_y, 3),
        )
        if abs(raw_center_x) > 1e-6:
            _transform_paths(
                paths,
                scale_factor=1.0,
                center_x=0.0,
                center_y=0.0,
                shift_x=-raw_center_x,
                shift_y=0.0,
            )

        local_bounds = _paths_bounds(paths)
        if local_bounds is None:
            active_logger.warning(
                "Text shape injection skipped layer=%s reason=failed_normalized_local_bounds text=%r",
                name_raw,
                text_value,
            )
            continue
        min_x, min_y, max_x, max_y = local_bounds
        text_width = max_x - min_x
        text_height = max_y - min_y
        local_cx = (min_x + max_x) / 2.0
        local_cy = (min_y + max_y) / 2.0
        text_lines = [chunk for chunk in re.split(r"\r\n|\r|\n", text_value) if chunk.strip()]
        is_single_line_text = len(text_lines) <= 1
        is_single_line_paragraph = style_ps is not None and is_single_line_text
        vertical_delta_y = -local_cy if is_single_line_paragraph else 0.0
        active_logger.info(
            (
                "Generated text normalized local bounds after_local_centering layer=%s paragraph_ps=%s paragraph_sz=%s j=%s "
                "min_x=%s min_y=%s max_x=%s max_y=%s text_width=%s text_height=%s center_x=%s center_y_before_correction=%s "
                "chosen_delta_y=%s single_line_paragraph=%s text_lines=%s"
            ),
            name_raw,
            _serialize_for_log(style_ps),
            _serialize_for_log(style_sz),
            justification,
            round(min_x, 3),
            round(min_y, 3),
            round(max_x, 3),
            round(max_y, 3),
            round(text_width, 3),
            round(text_height, 3),
            round(local_cx, 6),
            round(local_cy, 6),
            round(vertical_delta_y, 6),
            is_single_line_paragraph,
            len(text_lines),
        )
        if style_ps is not None and style_sz is not None:
            if justification == 2:
                chosen_target_x = style_ps[0] + (style_sz[0] / 2.0)
                paragraph_delta_x = chosen_target_x
                local_offset_y = vertical_delta_y
                local_align_reason = "paragraph_center_align_target_x_preserved_after_normalization"
                x_offset_source = "paragraph_layout_center"
            elif justification == 1:
                chosen_target_x = style_ps[0] + style_sz[0]
                paragraph_delta_x = chosen_target_x - (text_width / 2.0)
                local_offset_y = vertical_delta_y
                local_align_reason = "paragraph_right_align_target_x_preserved_after_normalization"
                x_offset_source = "paragraph_layout_right"
            else:
                chosen_target_x = style_ps[0]
                paragraph_delta_x = chosen_target_x + (text_width / 2.0)
                local_offset_y = vertical_delta_y
                local_align_reason = "paragraph_left_align_target_x_preserved_after_normalization"
                x_offset_source = "paragraph_layout_left"
        elif style_ps is not None:
            chosen_target_x = style_ps[0]
            paragraph_delta_x = chosen_target_x
            local_offset_y = vertical_delta_y
            local_align_reason = "paragraph_no_box_target_x_preserved_after_normalization"
            x_offset_source = "paragraph_layout_no_box"
        else:
            chosen_target_x = box_center_x
            paragraph_delta_x = box_center_x - local_cx
            local_offset_y = box_center_y - local_cy
            local_align_reason = "default_box_center_delta"
            x_offset_source = "fallback_box_center"
        source_local_px = float(source_local_p[0]) if source_local_p is not None else 0.0
        has_non_zero_anchor = abs(source_local_a3[0]) > 1e-3 or abs(source_local_a3[1]) > 1e-3
        has_non_unity_scale = abs(source_local_s3[0] - 100.0) > 1e-3 or abs(source_local_s3[1] - 100.0) > 1e-3
        has_preserved_parent_geometry = has_parent_chain and (has_non_zero_anchor or has_non_unity_scale)
        if x_mode == "local_paragraph_delta_only":
            x_profile = "absolute_profile"
            x_formula = "absolute_paragraph_target"
            x_from_preserved_layer_ks = False
            local_offset_x = paragraph_delta_x
        else:
            if has_non_zero_anchor or has_non_unity_scale or has_preserved_parent_geometry:
                x_profile = "geometry_fallback_profile"
                x_formula = "absolute_paragraph_target_geometry_fallback"
                x_from_preserved_layer_ks = False
                local_offset_x = paragraph_delta_x
            else:
                x_profile = "legacy_preserved_profile"
                x_formula = "paragraph_plus_preserved_ks"
                x_from_preserved_layer_ks = True
                local_offset_x = paragraph_delta_x + source_local_px
        active_logger.info(
            (
                "Computed paragraph X delta layer=%s chosen_target_x=%s computed_delta_x_before_final_write=%s "
                "computed_delta_y_before_final_write=%s reason=%s x_source=%s source_local_p.x=%s "
                "x_no_longer_zeroed_after_normalization=%s x_mode=%s x_profile=%s x_formula=%s "
                "geometry_anchor=%s geometry_scale=%s geometry_parent=%s "
                "single_x_strategy_locked=%s"
            ),
            name_raw,
            round(chosen_target_x, 6),
            round(local_offset_x, 6),
            round(local_offset_y, 6),
            local_align_reason,
            x_offset_source,
            round(source_local_px, 6),
            abs(local_offset_x) > 1e-9,
            x_mode,
            x_profile,
            x_formula,
            has_non_zero_anchor,
            has_non_unity_scale,
            has_preserved_parent_geometry,
            True,
        )
        normalized_min_x = min_x + local_offset_x
        normalized_max_x = max_x + local_offset_x
        normalized_min_y = min_y + local_offset_y
        normalized_max_y = max_y + local_offset_y
        normalized_center_x = (normalized_min_x + normalized_max_x) / 2.0
        normalized_center_y = (normalized_min_y + normalized_max_y) / 2.0
        active_logger.info(
            (
                "Generated text normalized local bounds layer=%s min_x=%s min_y=%s max_x=%s max_y=%s "
                "center=[%s,%s] computed_glyph_center=[%s,%s] computed_delta_x=%s computed_delta_y=%s "
                "reason=%s bounds_after_y_correction=[%s,%s] final_applied_group_offset=[%s,%s] "
                "ps=%s sz=%s j=%s confirm_paths_not_absolute=%s no_hardcoded_coordinates=%s"
            ),
            name_raw,
            round(normalized_min_x, 3),
            round(normalized_min_y, 3),
            round(normalized_max_x, 3),
            round(normalized_max_y, 3),
            round(normalized_center_x, 3),
            round(normalized_center_y, 3),
            round(local_cx, 3),
            round(local_cy, 3),
            round(local_offset_x, 3),
            round(local_offset_y, 3),
            local_align_reason,
            round(normalized_min_y, 3),
            round(normalized_max_y, 3),
            round(local_offset_x, 3),
            round(local_offset_y, 3),
            _serialize_for_log(style_ps),
            _serialize_for_log(style_sz),
            justification,
            True,
            True,
        )

        shape_items: list[dict[str, Any]] = []
        for path_index, path in enumerate(paths):
            shape_items.append(
                {
                    "ty": "sh",
                    "ind": path_index,
                    "ix": path_index + 1,
                    "nm": f"Path {path_index + 1}",
                    "mn": "ADBE Vector Shape - Group",
                    "ks": {"a": 0, "k": path},
                    "hd": False,
                }
            )

        fill_item: dict[str, Any] = {
            "ty": "fl",
            "nm": "Fill 1",
            "mn": "ADBE Vector Graphic - Fill",
            "c": {"a": 0, "k": fill_rgba},
            "o": {"a": 0, "k": 100},
            "r": 1,
            "bm": 0,
            "hd": False,
        }
        shape_items.append(fill_item)
        if stroke_rgba is not None and stroke_width > 0:
            shape_items.append(
                {
                    "ty": "st",
                    "nm": "Stroke 1",
                    "mn": "ADBE Vector Graphic - Stroke",
                    "c": {"a": 0, "k": stroke_rgba},
                    "o": {"a": 0, "k": 100},
                    "w": {"a": 0, "k": stroke_width},
                    "lc": 2,
                    "lj": 2,
                    "ml": 4,
                    "bm": 0,
                    "hd": False,
                }
            )

        shape_items.append(
            {
                "ty": "tr",
                "nm": "Transform",
                "p": {"a": 0, "k": [round(local_offset_x, 6), round(local_offset_y, 6)]},
                "a": {"a": 0, "k": [0, 0]},
                "s": {"a": 0, "k": [100, 100]},
                "r": {"a": 0, "k": 0},
                "o": {"a": 0, "k": 100},
                "sk": {"a": 0, "k": 0},
                "sa": {"a": 0, "k": 0},
            }
        )

        generated_layer = copy.deepcopy(layer)
        generated_layer["ty"] = 4
        generated_layer["nm"] = f"{name_raw}{GENERATED_TEXT_SHAPE_LAYER_SUFFIX}"
        generated_layer.pop("t", None)
        generated_group = {
            "ty": "gr",
            "nm": "Generated Text Shapes",
            "np": len(shape_items),
            "cix": 2,
            "bm": 0,
            "ix": 1,
            "mn": "ADBE Vector Group",
            "hd": False,
            "it": shape_items,
        }
        generated_layer["shapes"] = [
            generated_group
        ]
        group_items = generated_group.get("it")
        if isinstance(group_items, list):
            tr_index: int | None = None
            tr_item: dict[str, Any] | None = None
            for item_index, item in enumerate(group_items):
                if not isinstance(item, dict):
                    continue
                if item.get("ty") == "tr":
                    tr_index = item_index
                    tr_item = item
                    break
            if tr_item is None:
                tr_item = {
                    "ty": "tr",
                    "nm": "Transform",
                    "p": {"a": 0, "k": [round(local_offset_x, 6), round(local_offset_y, 6)]},
                    "a": {"a": 0, "k": [0, 0]},
                    "s": {"a": 0, "k": [100, 100]},
                    "r": {"a": 0, "k": 0},
                    "o": {"a": 0, "k": 100},
                    "sk": {"a": 0, "k": 0},
                    "sa": {"a": 0, "k": 0},
                }
                group_items.append(tr_item)
                tr_index = len(group_items) - 1
            else:
                tr_item["p"] = {"a": 0, "k": [round(local_offset_x, 6), round(local_offset_y, 6)]}

            if tr_index is not None and tr_index != len(group_items) - 1:
                moved_tr = group_items.pop(tr_index)
                group_items.append(moved_tr)
                tr_item = moved_tr
            active_logger.info(
                "Generated text group transform final layer=%s tr.p=%s tr_index=%s items=%s",
                generated_layer.get("nm"),
                _serialize_for_log(tr_item.get("p") if isinstance(tr_item, dict) else None),
                (len(group_items) - 1),
                len(group_items),
            )

        source_local_p3 = _eval_position_prop_at_t(source_local_ks.get("p"), 0.0, [0.0, 0.0, 0.0])
        source_local_a3 = _to_vec3(_extract_animatable_value(source_local_ks.get("a")), [0.0, 0.0, 0.0])
        source_local_s3 = _to_vec3(_extract_animatable_value(source_local_ks.get("s")), [100.0, 100.0, 100.0])
        source_local_r = _to_scalar(_extract_animatable_value(source_local_ks.get("r")), 0.0)
        source_local_o = _to_scalar(_extract_animatable_value(source_local_ks.get("o")), 100.0)
        active_logger.info(
            "Source text local transform layer=%s parent=%s ks.p=%s ks.a=%s ks.s=%s ks.r=%s ks.o=%s",
            name_raw,
            layer.get("parent"),
            _serialize_for_log(source_local_p3),
            _serialize_for_log(source_local_a3),
            _serialize_for_log(source_local_s3),
            source_local_r,
            source_local_o,
        )

        generated_layer["ks"] = copy.deepcopy(source_local_ks)
        if "parent" in layer:
            generated_layer["parent"] = layer.get("parent")
        active_logger.info(
            "Preserved source transform chain layer=%s strategy=preserve_parent_and_layer_ks parent=%s layer_transform_bake_disabled=%s",
            name_raw,
            generated_layer.get("parent"),
            True,
        )
        final_group_tr_p: Any = None
        final_group_items = generated_group.get("it")
        if isinstance(final_group_items, list):
            for final_item in final_group_items:
                if isinstance(final_item, dict) and final_item.get("ty") == "tr":
                    final_group_tr_p = final_item.get("p")
                    break
        active_logger.info(
            (
                "Final group transform write before_comp_correction layer=%s chosen_target_x=%s computed_delta_x_before_final_write=%s "
                "final_tr.p=%s source_ks.p=%s x_source=%s source_local_p.x=%s "
                "x_from_preserved_layer_ks=%s x_mode=%s x_profile=%s x_formula=%s single_x_strategy_locked=%s"
            ),
            generated_layer.get("nm"),
            round(chosen_target_x, 6),
            round(local_offset_x, 6),
            _serialize_for_log(final_group_tr_p),
            _serialize_for_log(source_local_p3),
            x_offset_source,
            round(source_local_px, 6),
            x_from_preserved_layer_ks,
            x_mode,
            x_profile,
            x_formula,
            True,
        )
        final_tr_p_x: float | None = None
        if isinstance(final_group_tr_p, dict):
            tr_k = final_group_tr_p.get("k")
            if isinstance(tr_k, list) and tr_k:
                final_tr_p_x = _as_float(tr_k[0])
        layer_matrix_2d = _compose_layer_matrix(
            source_local_p3,
            source_local_a3,
            source_local_s3,
            source_local_r,
        )
        layer_center_xy = _mat_apply_to_point_2d(
            layer_matrix_2d,
            float(normalized_center_x),
            float(normalized_center_y),
        )
        comp_center_xy, chain_debug = _project_local_point_to_comp_space(
            source_layer=layer,
            layers_by_ind=layers_by_ind,
            point_xy=(float(normalized_center_x), float(normalized_center_y)),
            t=0.0,
        )
        comp_w = _as_float(data.get("w"))
        comp_h = _as_float(data.get("h"))
        if comp_w is not None and comp_h is not None:
            comp_target_x = comp_w / 2.0
            comp_target_y = comp_h / 2.0
            comp_delta_x = comp_center_xy[0] - comp_target_x
            comp_delta_y = comp_center_xy[1] - comp_target_y
        else:
            comp_target_x = None
            comp_target_y = None
            comp_delta_x = None
            comp_delta_y = None
        active_logger.info(
            (
                "Visual center debug layer=%s local_group_center=[%s,%s] layer_space_center=[%s,%s] comp_center=[%s,%s] "
                "comp_target_center=[%s,%s] comp_delta=[%s,%s] chain=%s"
            ),
            generated_layer.get("nm"),
            round(normalized_center_x, 6),
            round(normalized_center_y, 6),
            round(layer_center_xy[0], 6),
            round(layer_center_xy[1], 6),
            round(comp_center_xy[0], 6),
            round(comp_center_xy[1], 6),
            (round(comp_target_x, 6) if comp_target_x is not None else None),
            (round(comp_target_y, 6) if comp_target_y is not None else None),
            (round(comp_delta_x, 6) if comp_delta_x is not None else None),
            (round(comp_delta_y, 6) if comp_delta_y is not None else None),
            chain_debug,
        )
        template_name_value = (template_name or str(data.get("__template_name__", ""))).strip()
        template_name_lc = template_name_value.lower()
        is_motion_preserving_comp_correction_template = template_name_lc in {
            _EMOJI3_TEMPLATE_FILE,
            _EMOJI8_TEMPLATE_FILE,
            _EMOJI14_TEMPLATE_FILE,
        }
        corrected_tr_p_x: float | None = None
        corrected_tr_p_y: float | None = None
        corrected_tr_p_x_before_skip: float | None = None
        comp_delta_x_after_correction: float | None = None
        comp_delta_y_after_correction: float | None = None
        local_delta_x: float | None = None
        local_delta_y: float | None = None
        correction_space = "none"
        world_matrix_linear: Any = None
        world_matrix_det: float | None = None
        parent_chain_summary: Any = None
        numeric_jacobian: Any = None
        numeric_jacobian_det: float | None = None
        comp_space_x_correction_applied = False
        if comp_delta_x is not None and isinstance(final_group_tr_p, dict):
            tr_k = final_group_tr_p.get("k")
            if isinstance(tr_k, list) and tr_k:
                current_tr_p_x = _as_float(tr_k[0])
                current_tr_p_y = _as_float(tr_k[1]) if len(tr_k) > 1 else None
                if current_tr_p_x is not None:
                    corrected_tr_p_x_before_skip = current_tr_p_x - comp_delta_x
                    if is_motion_preserving_comp_correction_template:
                        local_delta_tuple = None
                        local_delta_debug: dict[str, Any] = {}
                        comp_dy_for_local = float(comp_delta_y) if comp_delta_y is not None else 0.0
                        local_delta_tuple, local_delta_debug = _project_comp_delta_to_local_delta(
                            source_layer=layer,
                            layers_by_ind=layers_by_ind,
                            comp_delta_xy=(float(comp_delta_x), comp_dy_for_local),
                            t=0.0,
                        )
                        world_matrix_linear = local_delta_debug.get("linear")
                        world_matrix_det = _as_float(local_delta_debug.get("det"))
                        parent_chain_summary = local_delta_debug.get("chain")
                        if local_delta_tuple is None:
                            local_delta_tuple, local_delta_debug = _project_comp_delta_to_local_delta_numeric(
                                source_layer=layer,
                                layers_by_ind=layers_by_ind,
                                base_local_xy=(float(normalized_center_x), float(normalized_center_y)),
                                comp_delta_xy=(float(comp_delta_x), comp_dy_for_local),
                                t=0.0,
                                eps=1.0,
                            )
                            numeric_jacobian = local_delta_debug.get("jacobian")
                            numeric_jacobian_det = _as_float(local_delta_debug.get("det"))
                            if local_delta_tuple is not None:
                                parent_chain_summary = local_delta_debug.get("chain", parent_chain_summary)
                                correction_space = "inverse_parent_chain_local_delta_numeric_fallback"
                        if local_delta_tuple is not None:
                            local_delta_x, local_delta_y = local_delta_tuple
                            current_tr_p_y_safe = 0.0 if current_tr_p_y is None else current_tr_p_y
                            corrected_tr_p_x = current_tr_p_x - local_delta_x
                            corrected_tr_p_y = current_tr_p_y_safe - local_delta_y
                            tr_k[0] = round(corrected_tr_p_x, 6)
                            if len(tr_k) > 1:
                                tr_k[1] = round(corrected_tr_p_y, 6)
                            else:
                                tr_k.append(round(corrected_tr_p_y, 6))
                            local_offset_x = corrected_tr_p_x
                            local_offset_y = corrected_tr_p_y
                            final_tr_p_x = corrected_tr_p_x
                            if correction_space == "none":
                                correction_space = "inverse_parent_chain_local_delta"
                            comp_space_x_correction_applied = True
                            corrected_local_center = (
                                float(normalized_center_x) - float(local_delta_x),
                                float(normalized_center_y) - float(local_delta_y),
                            )
                            comp_center_after_correction, _ = _project_local_point_to_comp_space(
                                source_layer=layer,
                                layers_by_ind=layers_by_ind,
                                point_xy=corrected_local_center,
                                t=0.0,
                            )
                            if comp_target_x is not None:
                                comp_delta_x_after_correction = comp_center_after_correction[0] - comp_target_x
                            if comp_target_y is not None:
                                comp_delta_y_after_correction = comp_center_after_correction[1] - comp_target_y
                        else:
                            correction_space = "inverse_parent_chain_local_delta_failed"
                            active_logger.warning(
                                (
                                    "Comp-space correction skipped layer=%s template_name=%s reason=%s "
                                    "world_matrix_linear=%s world_matrix_det=%s "
                                    "numeric_jacobian=%s numeric_jacobian_det=%s parent_chain_summary=%s"
                                ),
                                generated_layer.get("nm"),
                                template_name_value or None,
                                "inverse_matrix_or_tr_p_invalid",
                                _serialize_for_log(world_matrix_linear),
                                (round(world_matrix_det, 12) if world_matrix_det is not None else None),
                                _serialize_for_log(numeric_jacobian),
                                (round(numeric_jacobian_det, 12) if numeric_jacobian_det is not None else None),
                                _serialize_for_log(parent_chain_summary),
                            )
                    else:
                        corrected_tr_p_x = corrected_tr_p_x_before_skip
                        tr_k[0] = round(corrected_tr_p_x, 6)
                        local_offset_x = corrected_tr_p_x
                        final_tr_p_x = corrected_tr_p_x
                        correction_space = "comp_space_x_subtract_direct"
                        comp_space_x_correction_applied = True
                        corrected_local_center = (
                            float(normalized_center_x) - float(comp_delta_x),
                            float(normalized_center_y),
                        )
                        comp_center_after_correction, _ = _project_local_point_to_comp_space(
                            source_layer=layer,
                            layers_by_ind=layers_by_ind,
                            point_xy=corrected_local_center,
                            t=0.0,
                        )
                        if comp_target_x is not None:
                            comp_delta_x_after_correction = comp_center_after_correction[0] - comp_target_x
        active_logger.info(
            (
                "Comp-space X correction layer=%s template_name=%s comp_space_x_correction_applied=%s "
                "comp_delta_x_before_correction=%s comp_delta_y_before_correction=%s corrected_tr_p_x_before_skip=%s "
                "corrected_tr_p_x=%s corrected_tr_p_y=%s local_delta_x=%s local_delta_y=%s "
                "comp_delta_x_after_correction=%s comp_delta_y_after_correction=%s "
                "correction_space=%s world_matrix_linear=%s world_matrix_det=%s "
                "numeric_jacobian=%s numeric_jacobian_det=%s parent_chain_summary=%s"
            ),
            generated_layer.get("nm"),
            template_name_value or None,
            comp_space_x_correction_applied,
            (round(comp_delta_x, 6) if comp_delta_x is not None else None),
            (round(comp_delta_y, 6) if comp_delta_y is not None else None),
            (round(corrected_tr_p_x_before_skip, 6) if corrected_tr_p_x_before_skip is not None else None),
            (round(corrected_tr_p_x, 6) if corrected_tr_p_x is not None else None),
            (round(corrected_tr_p_y, 6) if corrected_tr_p_y is not None else None),
            (round(local_delta_x, 6) if local_delta_x is not None else None),
            (round(local_delta_y, 6) if local_delta_y is not None else None),
            (round(comp_delta_x_after_correction, 6) if comp_delta_x_after_correction is not None else None),
            (round(comp_delta_y_after_correction, 6) if comp_delta_y_after_correction is not None else None),
            correction_space,
            _serialize_for_log(world_matrix_linear),
            (round(world_matrix_det, 12) if world_matrix_det is not None else None),
            _serialize_for_log(numeric_jacobian),
            (round(numeric_jacobian_det, 12) if numeric_jacobian_det is not None else None),
            _serialize_for_log(parent_chain_summary),
        )
        template_extra_x_nudge = 0.0
        if template_name_lc == _EMOJI2_TEMPLATE_FILE:
            template_extra_x_nudge = _EMOJI2_TEMPLATE_EXTRA_X_NUDGE
        corrected_tr_p_x_before_template_nudge = final_tr_p_x
        base_final_tr_p_x = final_tr_p_x
        if abs(template_extra_x_nudge) > 1e-9 and isinstance(final_group_tr_p, dict):
            tr_k = final_group_tr_p.get("k")
            if isinstance(tr_k, list) and tr_k:
                base_x = _as_float(tr_k[0])
                if base_x is not None:
                    nudged_x = base_x + template_extra_x_nudge
                    tr_k[0] = round(nudged_x, 6)
                    local_offset_x = nudged_x
                    final_tr_p_x = nudged_x
        desired_visual_x_nudge_px = 0.0
        computed_local_x_nudge: float | None = None
        final_tr_p_x_before_visual_nudge = final_tr_p_x
        if template_name_lc == _EMOJI4_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI4_TEMPLATE_EXTRA_X_NUDGE
        elif template_name_lc == _EMOJI8_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI8_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI8_NESTED_TEXT_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI8_NESTED_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI9_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI9_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI10_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI10_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI11_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI11_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI13_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI13_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI15_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI15_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI16_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI16_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI18_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI18_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI19_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI19_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI20_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI20_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI21_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI21_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI22_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI22_VISUAL_X_NUDGE_PX
        elif template_name_lc == _EMOJI24_TEMPLATE_FILE:
            desired_visual_x_nudge_px = _EMOJI24_VISUAL_X_NUDGE_PX
        if abs(desired_visual_x_nudge_px) > 1e-9 and isinstance(final_group_tr_p, dict):
            tr_k = final_group_tr_p.get("k")
            if isinstance(tr_k, list) and tr_k:
                base_x = _as_float(tr_k[0])
                if base_x is not None:
                    visual_local_delta, _visual_debug = _project_comp_delta_to_local_delta(
                        source_layer=layer,
                        layers_by_ind=layers_by_ind,
                        comp_delta_xy=(float(desired_visual_x_nudge_px), 0.0),
                        t=0.0,
                    )
                    if visual_local_delta is None:
                        visual_local_delta, _visual_debug = _project_comp_delta_to_local_delta_numeric(
                            source_layer=layer,
                            layers_by_ind=layers_by_ind,
                            base_local_xy=(float(normalized_center_x), float(normalized_center_y)),
                            comp_delta_xy=(float(desired_visual_x_nudge_px), 0.0),
                            t=0.0,
                            eps=1.0,
                        )
                    if visual_local_delta is not None:
                        computed_local_x_nudge = float(visual_local_delta[0])
                    else:
                        computed_local_x_nudge = float(desired_visual_x_nudge_px)
                    visual_nudged_x = base_x + computed_local_x_nudge
                    tr_k[0] = round(visual_nudged_x, 6)
                    local_offset_x = visual_nudged_x
                    final_tr_p_x = visual_nudged_x
        active_logger.info(
            "Template visual X nudge template_name=%s desired_visual_x_nudge_px=%s computed_local_x_nudge=%s final_tr_p_x_before_visual_nudge=%s final_tr_p_x_after_visual_nudge=%s",
            template_name_value or None,
            round(desired_visual_x_nudge_px, 6),
            (round(computed_local_x_nudge, 6) if computed_local_x_nudge is not None else None),
            (round(final_tr_p_x_before_visual_nudge, 6) if final_tr_p_x_before_visual_nudge is not None else None),
            (round(final_tr_p_x, 6) if final_tr_p_x is not None else None),
        )
        desired_visual_y_nudge_px = 0.0
        final_tr_p_y_before_visual_nudge: float | None = None
        final_tr_p_y_after_visual_nudge: float | None = None
        if template_name_lc == _ZHOPBOL2_TEMPLATE_FILE:
            desired_visual_y_nudge_px = _ZHOPBOL2_VISUAL_Y_NUDGE_PX
        elif template_name_lc == _EMOJI6_TEMPLATE_FILE:
            desired_visual_y_nudge_px = _EMOJI6_VISUAL_Y_NUDGE_PX
        elif template_name_lc == _EMOJI8_TEMPLATE_FILE:
            desired_visual_y_nudge_px = _EMOJI8_VISUAL_Y_NUDGE_PX
        elif template_name_lc == _EMOJI11_TEMPLATE_FILE:
            desired_visual_y_nudge_px = _EMOJI11_VISUAL_Y_NUDGE_PX
        elif template_name_lc == _EMOJI17_TEMPLATE_FILE:
            desired_visual_y_nudge_px = _EMOJI17_VISUAL_Y_NUDGE_PX
        if abs(desired_visual_y_nudge_px) > 1e-9 and isinstance(final_group_tr_p, dict):
            tr_k = final_group_tr_p.get("k")
            if isinstance(tr_k, list):
                current_y = _as_float(tr_k[1]) if len(tr_k) > 1 else None
                if current_y is not None:
                    final_tr_p_y_before_visual_nudge = current_y
                    visual_local_delta_y = None
                    visual_local_delta, _visual_y_debug = _project_comp_delta_to_local_delta(
                        source_layer=layer,
                        layers_by_ind=layers_by_ind,
                        comp_delta_xy=(0.0, float(desired_visual_y_nudge_px)),
                        t=0.0,
                    )
                    if visual_local_delta is None:
                        visual_local_delta, _visual_y_debug = _project_comp_delta_to_local_delta_numeric(
                            source_layer=layer,
                            layers_by_ind=layers_by_ind,
                            base_local_xy=(float(normalized_center_x), float(normalized_center_y)),
                            comp_delta_xy=(0.0, float(desired_visual_y_nudge_px)),
                            t=0.0,
                            eps=1.0,
                        )
                    if visual_local_delta is not None:
                        visual_local_delta_y = float(visual_local_delta[1])
                    else:
                        visual_local_delta_y = float(desired_visual_y_nudge_px)
                    nudged_y = current_y + visual_local_delta_y
                    tr_k[1] = round(nudged_y, 6)
                    local_offset_y = nudged_y
                    final_tr_p_y_after_visual_nudge = nudged_y
        active_logger.info(
            "Template visual Y nudge template_name=%s desired_visual_y_nudge_px=%s final_tr_p_y_before_visual_nudge=%s final_tr_p_y_after_visual_nudge=%s",
            template_name_value or None,
            round(desired_visual_y_nudge_px, 6),
            (round(final_tr_p_y_before_visual_nudge, 6) if final_tr_p_y_before_visual_nudge is not None else None),
            (round(final_tr_p_y_after_visual_nudge, 6) if final_tr_p_y_after_visual_nudge is not None else None),
        )
        active_logger.info(
            "Template X nudge template_name=%s base_final_tr_p_x=%s corrected_tr_p_x_before_template_nudge=%s template_extra_x_nudge=%s final_tr_p_x_after_template_nudge=%s",
            template_name_value or None,
            (round(base_final_tr_p_x, 6) if base_final_tr_p_x is not None else None),
            (
                round(corrected_tr_p_x_before_template_nudge, 6)
                if corrected_tr_p_x_before_template_nudge is not None
                else None
            ),
            round(template_extra_x_nudge, 6),
            (round(final_tr_p_x, 6) if final_tr_p_x is not None else None),
        )
        active_logger.info(
            "Template strategy result template_name=%s comp_space_x_correction_applied=%s corrected_tr_p_x_before_skip=%s final_tr_p_x_after_template_strategy=%s",
            template_name_value or None,
            comp_space_x_correction_applied,
            (round(corrected_tr_p_x_before_skip, 6) if corrected_tr_p_x_before_skip is not None else None),
            (round(final_tr_p_x, 6) if final_tr_p_x is not None else None),
        )
        active_logger.info(
            "Final group transform write after_comp_correction layer=%s final_tr.p=%s corrected_tr_p_x=%s",
            generated_layer.get("nm"),
            _serialize_for_log(final_group_tr_p),
            (round(final_tr_p_x, 6) if final_tr_p_x is not None else None),
        )
        if template_name_lc == _EMOJI8_TEMPLATE_FILE:
            motion_inheritance_preserved = correction_space.startswith("inverse_parent_chain_local_delta")
            active_logger.info(
                (
                    "Emoji7 final placement template_name=%s final_font_size=%s "
                    "desired_visual_x_nudge_px=%s desired_visual_y_nudge_px=%s correction_space=%s "
                    "parent=%s final_tr_p_after_correction=%s motion_inheritance_preserved=%s"
                ),
                template_name_value or None,
                round(font_size, 6),
                round(desired_visual_x_nudge_px, 6),
                round(desired_visual_y_nudge_px, 6),
                correction_space,
                generated_layer.get("parent"),
                _serialize_for_log(final_group_tr_p),
                motion_inheritance_preserved,
            )
        marker_id = uuid.uuid4().hex[:10]
        marker_payload = {
            "marker_id": marker_id,
            "x_mode": x_mode,
            "x_profile": x_profile,
            "x_formula": x_formula,
            "chosen_target_x": chosen_target_x,
            "source_ks_p_x": source_local_px,
            "final_tr_p_x": final_tr_p_x,
            "single_x_strategy_locked": True,
            "layer": generated_layer.get("nm"),
        }
        marker_token = str(data.get(_X_MARKER_TOKEN_KEY) or uuid.uuid4().hex[:16])
        data[_X_MARKER_TOKEN_KEY] = marker_token
        marker_payload["marker_token"] = marker_token
        with _X_RENDER_MARKER_LOCK:
            _LAST_X_RENDER_MARKER = copy.deepcopy(marker_payload)
            _X_RENDER_MARKER_BY_TOKEN[marker_token] = copy.deepcopy(marker_payload)
        active_logger.info(
            "X placement marker marker_id=%s x_mode=%s x_profile=%s x_formula=%s chosen_target_x=%s source_ks_p_x=%s final_tr_p_x=%s single_x_strategy_locked=%s layer=%s",
            marker_id,
            x_mode,
            x_profile,
            x_formula,
            round(chosen_target_x, 6),
            round(source_local_px, 6),
            (round(final_tr_p_x, 6) if final_tr_p_x is not None else None),
            True,
            generated_layer.get("nm"),
        )

        if DEBUG_GENERATED_SHAPE_LAYER:
            generated_layer["hd"] = False

            group_items = generated_group.get("it")
            if not isinstance(group_items, list):
                group_items = []
                generated_group["it"] = group_items

            fill_item_ref: dict[str, Any] | None = None
            stroke_item_ref: dict[str, Any] | None = None
            tr_item_ref: dict[str, Any] | None = None
            for item in group_items:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("ty")
                if item_type == "fl" and fill_item_ref is None:
                    fill_item_ref = item
                elif item_type == "st" and stroke_item_ref is None:
                    stroke_item_ref = item
                elif item_type == "tr" and tr_item_ref is None:
                    tr_item_ref = item

            if fill_item_ref is None:
                fill_item_ref = {
                    "ty": "fl",
                    "nm": "Fill 1",
                    "mn": "ADBE Vector Graphic - Fill",
                    "r": 1,
                    "bm": 0,
                    "hd": False,
                }
                group_items.append(fill_item_ref)
            fill_item_ref["c"] = {"a": 0, "k": [1.0, 1.0, 1.0, 1.0]}
            fill_item_ref["o"] = {"a": 0, "k": 100}
            fill_item_ref["hd"] = False

            if stroke_item_ref is None:
                stroke_item_ref = {
                    "ty": "st",
                    "nm": "Stroke 1",
                    "mn": "ADBE Vector Graphic - Stroke",
                    "lc": 2,
                    "lj": 2,
                    "ml": 4,
                    "bm": 0,
                    "hd": False,
                }
                group_items.append(stroke_item_ref)
            stroke_item_ref["c"] = {"a": 0, "k": [1.0, 0.0, 0.0, 1.0]}
            stroke_item_ref["o"] = {"a": 0, "k": 100}
            stroke_item_ref["w"] = {"a": 0, "k": 6}
            stroke_item_ref["lc"] = 2
            stroke_item_ref["lj"] = 2
            stroke_item_ref["ml"] = 4
            stroke_item_ref["hd"] = False

            if tr_item_ref is None:
                tr_item_ref = {
                    "ty": "tr",
                    "nm": "Transform",
                }
                group_items.append(tr_item_ref)
            tr_item_ref["p"] = {"a": 0, "k": [round(local_offset_x, 6), round(local_offset_y, 6)]}
            tr_item_ref["a"] = {"a": 0, "k": [0, 0]}
            tr_item_ref["s"] = {"a": 0, "k": [100, 100]}
            tr_item_ref["r"] = {"a": 0, "k": 0}
            tr_item_ref["o"] = {"a": 0, "k": 100}
            tr_item_ref["sk"] = {"a": 0, "k": 0}
            tr_item_ref["sa"] = {"a": 0, "k": 0}

        layer_ks = generated_layer.get("ks")
        layer_ks_p = _extract_animatable_value(layer_ks.get("p")) if isinstance(layer_ks, dict) else None
        layer_ks_a = _extract_animatable_value(layer_ks.get("a")) if isinstance(layer_ks, dict) else None
        layer_ks_s = _extract_animatable_value(layer_ks.get("s")) if isinstance(layer_ks, dict) else None
        layer_ks_r = _extract_animatable_value(layer_ks.get("r")) if isinstance(layer_ks, dict) else None
        layer_ks_o = _extract_animatable_value(layer_ks.get("o")) if isinstance(layer_ks, dict) else None
        active_logger.info(
            "Generated shape transform strategy layer=%s strategy=preserve_parent_and_layer_ks parent=%s",
            generated_layer.get("nm"),
            generated_layer.get("parent"),
        )

        shapes_array = generated_layer.get("shapes")
        shape_group_it = generated_group.get("it") if isinstance(generated_group, dict) else None
        has_path = False
        has_fl = False
        has_st = False
        has_tr = False
        if isinstance(shape_group_it, list):
            for item in shape_group_it:
                if not isinstance(item, dict):
                    continue
                item_ty = item.get("ty")
                if item_ty == "sh":
                    has_path = True
                elif item_ty == "fl":
                    has_fl = True
                elif item_ty == "st":
                    has_st = True
                elif item_ty == "tr":
                    has_tr = True

        active_logger.info(
            (
                "Generated shape layer debug layer=%s parent=%s ks.p=%s ks.a=%s ks.s=%s ks.r=%s ks.o=%s "
                "hd=%s ip=%s op=%s st=%s shapes_count=%s debug_mode=%s"
            ),
            generated_layer.get("nm"),
            generated_layer.get("parent"),
            _serialize_for_log(layer_ks_p),
            _serialize_for_log(layer_ks_a),
            _serialize_for_log(layer_ks_s),
            _serialize_for_log(layer_ks_r),
            _serialize_for_log(layer_ks_o),
            generated_layer.get("hd"),
            generated_layer.get("ip"),
            generated_layer.get("op"),
            generated_layer.get("st"),
            len(shapes_array) if isinstance(shapes_array, list) else 0,
            DEBUG_GENERATED_SHAPE_LAYER,
        )
        active_logger.info(
            "Generated shape group debug layer=%s has_path=%s has_fl=%s has_st=%s has_tr=%s items=%s",
            generated_layer.get("nm"),
            has_path,
            has_fl,
            has_st,
            has_tr,
            len(shape_group_it) if isinstance(shape_group_it, list) else 0,
        )

        generated_layer.pop("tt", None)
        generated_layer.pop("td", None)
        generated_layer.pop("hasMask", None)
        generated_layer.pop("masksProperties", None)
        layers[index] = generated_layer
        original_index = index
        target_render_index = 0 if GENERATED_LAYER_RENDER_ORDER != "first_to_last" else (len(layers) - 1)
        moved_after_conversion = False
        if 0 <= original_index < len(layers) and 0 <= target_render_index < len(layers) and original_index != target_render_index:
            extracted_layer = layers.pop(original_index)
            layers.insert(target_render_index, extracted_layer)
            moved_after_conversion = True
        final_index = target_render_index if moved_after_conversion else original_index
        if not (0 <= final_index < len(layers)):
            final_index = max(0, min(len(layers) - 1, final_index))
        final_generated_layer = layers[final_index] if (0 <= final_index < len(layers) and isinstance(layers[final_index], dict)) else generated_layer
        if template_name_value.lower() == _EMOJI6_TEMPLATE_FILE:
            overlay_anchor_index: int | None = None
            overlay_anchor_name: str | None = None
            for candidate_index, candidate_layer in enumerate(layers):
                if candidate_index == final_index or not isinstance(candidate_layer, dict):
                    continue
                candidate_name = str(candidate_layer.get("nm", "")).strip()
                if "фигура 22" in _normalize_name(candidate_name):
                    overlay_anchor_index = candidate_index
                    overlay_anchor_name = candidate_name
                    break
            if overlay_anchor_index is not None:
                if GENERATED_LAYER_RENDER_ORDER == "first_to_last":
                    desired_final_index = overlay_anchor_index - 1
                else:
                    desired_final_index = overlay_anchor_index + 1
                desired_final_index = max(0, min(len(layers) - 1, desired_final_index))
                if desired_final_index != final_index:
                    moved_layer = layers.pop(final_index)
                    if desired_final_index > final_index:
                        desired_final_index -= 1
                    layers.insert(desired_final_index, moved_layer)
                    moved_after_conversion = True
                    final_index = desired_final_index
                    final_generated_layer = moved_layer
                    active_logger.info(
                        "Emoji6 stacking override template_name=%s overlay_anchor=%s overlay_anchor_index=%s final_generated_index=%s reason=keep_overlay_above_text",
                        template_name_value or None,
                        overlay_anchor_name,
                        overlay_anchor_index,
                        final_index,
                    )
        elif template_name_value.lower() == _EMOJI15_TEMPLATE_FILE:
            overlay_anchor_index: int | None = None
            fallback_anchor_index: int | None = None
            for candidate_index, candidate_layer in enumerate(layers):
                if candidate_index == final_index or not isinstance(candidate_layer, dict):
                    continue
                candidate_name = str(candidate_layer.get("nm", "")).strip()
                candidate_ind = candidate_layer.get("ind")
                if candidate_ind == 46:
                    overlay_anchor_index = candidate_index
                    break
                if _normalize_name(candidate_name) == "слой фигура 2":
                    fallback_anchor_index = candidate_index
            if overlay_anchor_index is None:
                overlay_anchor_index = fallback_anchor_index
            if overlay_anchor_index is not None:
                if GENERATED_LAYER_RENDER_ORDER == "first_to_last":
                    desired_final_index = overlay_anchor_index + 1
                else:
                    desired_final_index = overlay_anchor_index
                desired_final_index = max(0, min(len(layers) - 1, desired_final_index))
            else:
                desired_final_index = len(layers) - 1 if GENERATED_LAYER_RENDER_ORDER != "first_to_last" else 0
            if desired_final_index != final_index:
                moved_layer = layers.pop(final_index)
                if desired_final_index > final_index:
                    desired_final_index -= 1
                layers.insert(desired_final_index, moved_layer)
                moved_after_conversion = True
                final_index = desired_final_index
                final_generated_layer = moved_layer
            active_logger.info(
                "Emoji15 stacking override template_name=%s final_generated_index=%s overlay_anchor_index=%s reason=under_most_layers_but_above_layer_46",
                template_name_value or None,
                final_index,
                overlay_anchor_index,
            )

        overlay_last_to_first = _overlay_counts(layers, range(0, final_index))
        overlay_first_to_last = _overlay_counts(layers, range(final_index + 1, len(layers)))
        around_start = max(0, final_index - 3)
        around_end = min(len(layers), final_index + 4)
        around_layers: list[str] = []
        for around_index in range(around_start, around_end):
            around_layer = layers[around_index]
            if not isinstance(around_layer, dict):
                around_layers.append(f"{around_index}:<invalid>")
                continue
            around_layers.append(
                f"{around_index}:{around_layer.get('nm')}|ty={around_layer.get('ty')}|ind={around_layer.get('ind')}|hd={around_layer.get('hd')}|parent={around_layer.get('parent')}"
            )

        hidden_overlay_layers: list[str] = []
        if DEBUG_HIDE_OVERLAY_LAYERS:
            if GENERATED_LAYER_RENDER_ORDER == "first_to_last":
                candidate_indexes = range(final_index + 1, len(layers))
            else:
                candidate_indexes = range(final_index - 1, -1, -1)
            for candidate_index in candidate_indexes:
                candidate_layer = layers[candidate_index]
                if not isinstance(candidate_layer, dict):
                    continue
                if candidate_layer.get("ty") != 4:
                    continue
                if candidate_layer.get("hd"):
                    continue
                candidate_layer["hd"] = True
                hidden_overlay_layers.append(
                    f"{candidate_index}:{candidate_layer.get('nm')}|ind={candidate_layer.get('ind')}"
                )
                if len(hidden_overlay_layers) >= 6:
                    break
            active_logger.info(
                "Generated layer overlay debug hidden_count=%s hidden_layers=%s",
                len(hidden_overlay_layers),
                hidden_overlay_layers,
            )

        active_logger.info(
            (
                "Generated layer stacking final_index=%s final_ind=%s moved_after_conversion=%s "
                "render_order_assumption=%s overlays_last_to_first=%s overlays_first_to_last=%s around=%s"
            ),
            final_index,
            final_generated_layer.get("ind") if isinstance(final_generated_layer, dict) else None,
            moved_after_conversion,
            GENERATED_LAYER_RENDER_ORDER,
            overlay_last_to_first,
            overlay_first_to_last,
            around_layers,
        )
        if template_name_value.lower() == _EMOJI6_TEMPLATE_FILE:
            active_logger.info(
                (
                    "Emoji6 final placement template_name=%s final_font_size=%s desired_visual_y_nudge_px=%s "
                    "final_tr_p_y_after_visual_nudge=%s final_shape_overlays_last_to_first=%s"
                ),
                template_name_value or None,
                round(font_size, 6),
                round(desired_visual_y_nudge_px, 6),
                (round(final_tr_p_y_after_visual_nudge, 6) if final_tr_p_y_after_visual_nudge is not None else None),
                overlay_last_to_first,
            )
        converted += 1
        active_logger.info(
            (
                "Text layer converted to shapes layer_index=%s old_nm=%s new_nm=%s text=%r "
                "font=%s size=%s tracking=%s paths=%s box_center=[%s,%s] box_size=[%s,%s]"
            ),
            index,
            name_raw,
            generated_layer["nm"],
            text_value,
            str(font_path),
            round(font_size, 3),
            round(tracking, 3),
            len(paths),
            box_center_x,
            box_center_y,
            box_max_width,
            box_max_height,
        )

    if converted == 0:
        active_logger.warning(
            "Text shape injection done converted=0 target_layer=%s",
            layer_name,
        )
    else:
        active_logger.info(
            "Text shape injection done converted=%s target_layer=%s",
            converted,
            layer_name,
        )
    return converted

def _summarize_lottie_structure(data: dict[str, Any]) -> dict[str, Any]:
    layers = data.get("layers")
    safe_layers = layers if isinstance(layers, list) else []
    layer_type_counts: dict[str, int] = {}
    shape_groups = 0
    shape_paths = 0
    text_layers = 0
    total_shapes_arrays = 0

    for layer in safe_layers:
        if not isinstance(layer, dict):
            continue
        layer_type = str(layer.get("ty"))
        layer_type_counts[layer_type] = layer_type_counts.get(layer_type, 0) + 1
        if layer.get("ty") == 5:
            text_layers += 1
        shapes = layer.get("shapes")
        if isinstance(shapes, list):
            total_shapes_arrays += 1
            for shape in shapes:
                if not isinstance(shape, dict):
                    continue
                if shape.get("ty") == "gr":
                    shape_groups += 1
                items = shape.get("it")
                if not isinstance(items, list):
                    continue
                for item in items:
                    if isinstance(item, dict) and item.get("ty") == "sh":
                        shape_paths += 1

    return {
        "root_keys": sorted(data.keys()),
        "layer_count": len(safe_layers),
        "layer_ty_counts": layer_type_counts,
        "text_layers": text_layers,
        "shape_layer_with_shapes": total_shapes_arrays,
        "shape_groups": shape_groups,
        "shape_paths": shape_paths,
    }


def _log_shape_pipeline_diff(
    *,
    before_data: dict[str, Any],
    after_data: dict[str, Any],
    logger: logging.Logger,
) -> None:
    before_summary = _summarize_lottie_structure(before_data)
    after_summary = _summarize_lottie_structure(after_data)
    logger.info(
        "Shape pipeline compare before=%s after=%s",
        before_summary,
        after_summary,
    )

    before_layers = before_data.get("layers")
    after_layers = after_data.get("layers")
    if not isinstance(before_layers, list) or not isinstance(after_layers, list):
        return

    before_by_ind = {
        layer.get("ind"): layer
        for layer in before_layers
        if isinstance(layer, dict) and layer.get("ind") is not None
    }
    after_by_ind = {
        layer.get("ind"): layer
        for layer in after_layers
        if isinstance(layer, dict) and layer.get("ind") is not None
    }

    for ind, before_layer in before_by_ind.items():
        after_layer = after_by_ind.get(ind)
        if after_layer is None:
            continue
        before_ty = before_layer.get("ty")
        after_ty = after_layer.get("ty")
        before_has_t = "t" in before_layer
        after_has_t = "t" in after_layer
        before_shapes = before_layer.get("shapes")
        after_shapes = after_layer.get("shapes")
        before_shape_len = len(before_shapes) if isinstance(before_shapes, list) else 0
        after_shape_len = len(after_shapes) if isinstance(after_shapes, list) else 0
        if (
            before_ty != after_ty
            or before_has_t != after_has_t
            or before_shape_len != after_shape_len
            or before_layer.get("nm") != after_layer.get("nm")
        ):
            logger.info(
                (
                    "Shape pipeline layer diff ind=%s before_nm=%s before_ty=%s before_has_t=%s before_shapes=%s "
                    "after_nm=%s after_ty=%s after_has_t=%s after_shapes=%s"
                ),
                ind,
                before_layer.get("nm"),
                before_ty,
                before_has_t,
                before_shape_len,
                after_layer.get("nm"),
                after_ty,
                after_has_t,
                after_shape_len,
            )


def _extract_layer_index_from_path(path: str) -> int | None:
    match = _LAYER_PATH_RE.match(path)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _resolve_layer_index(
    path: str,
    node: dict[str, Any],
    top_layers: list[Any],
) -> int | None:
    path_index = _extract_layer_index_from_path(path)
    if path_index is not None and 0 <= path_index < len(top_layers):
        return path_index
    for index, candidate in enumerate(top_layers):
        if candidate is node:
            return index
    return None


def _layer_has_mask(layer: dict[str, Any]) -> bool:
    return bool(layer.get("hasMask")) or bool(layer.get("masksProperties"))


def _layer_is_hidden(layer: dict[str, Any]) -> bool:
    return bool(layer.get("hd"))


def _count_non_glyph_text_layers_anywhere(node: Any) -> int:
    count = 0
    stack: list[Any] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if current.get("ty") == 5 and not _is_glyph_bank_layer(str(current.get("nm", "")).strip()):
                count += 1
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return count


def _layer_ks_value(layer: dict[str, Any], key: str) -> Any:
    ks = layer.get("ks")
    if isinstance(ks, dict):
        return _extract_animatable_value(ks.get(key))
    return None


def _overlay_counts(top_layers: list[Any], indexes: range) -> dict[str, int]:
    counts = {"render": 0, "shape": 0, "solid": 0, "matte": 0, "mask": 0}
    for index in indexes:
        if not (0 <= index < len(top_layers)):
            continue
        layer = top_layers[index]
        if not isinstance(layer, dict):
            continue
        if _layer_is_hidden(layer):
            continue

        layer_type = layer.get("ty")
        if layer_type in _RENDERABLE_LAYER_TYPES:
            counts["render"] += 1
        if layer_type == 4:
            counts["shape"] += 1
        if layer_type == 1:
            counts["solid"] += 1
        if layer.get("tt") is not None or layer.get("td") is not None:
            counts["matte"] += 1
        if _layer_has_mask(layer):
            counts["mask"] += 1
    return counts


def _log_text_layer_diagnostics(
    *,
    logger: logging.Logger,
    path: str,
    layer: dict[str, Any],
    layer_name: str,
    layer_index: int | None,
    top_layers: list[Any],
    layers_by_ind: dict[int, tuple[int, dict[str, Any]]],
) -> None:
    display_name = layer_name or "<unnamed>"
    ks_o = _layer_ks_value(layer, "o")
    has_mask_flag = bool(layer.get("hasMask"))
    has_masks_properties = bool(layer.get("masksProperties"))

    logger.info(
        (
            "Text layer meta path=%s layer_index=%s ind=%s nm=%s ty=%s parent=%s "
            "ks.o=%s tt=%s td=%s ip=%s op=%s st=%s hasMask=%s masksProperties=%s hd=%s"
        ),
        path,
        layer_index,
        layer.get("ind"),
        display_name,
        layer.get("ty"),
        layer.get("parent"),
        _serialize_for_log(ks_o),
        layer.get("tt"),
        layer.get("td"),
        layer.get("ip"),
        layer.get("op"),
        layer.get("st"),
        has_mask_flag,
        has_masks_properties,
        layer.get("hd"),
    )

    parent_id = _as_int(layer.get("parent"))
    if parent_id not in (None, 0):
        parent_tuple = layers_by_ind.get(parent_id)
        if parent_tuple is None:
            logger.warning(
                "Text layer parent not found path=%s layer=%s parent_id=%s",
                path,
                display_name,
                parent_id,
            )
        else:
            parent_index, parent_layer = parent_tuple
            logger.info(
                (
                    "Text layer parent path=%s layer=%s parent_id=%s parent_index=%s parent_nm=%s parent_ty=%s "
                    "parent_ks.p=%s parent_ks.s=%s parent_ks.a=%s parent_ks.r=%s parent_ks.o=%s"
                ),
                path,
                display_name,
                parent_id,
                parent_index,
                parent_layer.get("nm"),
                parent_layer.get("ty"),
                _serialize_for_log(_layer_ks_value(parent_layer, "p")),
                _serialize_for_log(_layer_ks_value(parent_layer, "s")),
                _serialize_for_log(_layer_ks_value(parent_layer, "a")),
                _serialize_for_log(_layer_ks_value(parent_layer, "r")),
                _serialize_for_log(_layer_ks_value(parent_layer, "o")),
            )

    if layer_index is not None and top_layers:
        for neighbor_index in range(layer_index - 2, layer_index + 3):
            if not (0 <= neighbor_index < len(top_layers)):
                logger.info(
                    "Text layer neighbor text_layer_index=%s neighbor_index=%s status=out_of_range",
                    layer_index,
                    neighbor_index,
                )
                continue

            neighbor = top_layers[neighbor_index]
            if not isinstance(neighbor, dict):
                logger.info(
                    "Text layer neighbor text_layer_index=%s neighbor_index=%s status=not_a_layer_object",
                    layer_index,
                    neighbor_index,
                )
                continue

            logger.info(
                (
                    "Text layer neighbor text_layer_index=%s neighbor_index=%s ind=%s nm=%s ty=%s "
                    "parent=%s hd=%s tt=%s td=%s hasMask=%s masksProperties=%s"
                ),
                layer_index,
                neighbor_index,
                neighbor.get("ind"),
                neighbor.get("nm"),
                neighbor.get("ty"),
                neighbor.get("parent"),
                neighbor.get("hd"),
                neighbor.get("tt"),
                neighbor.get("td"),
                bool(neighbor.get("hasMask")),
                bool(neighbor.get("masksProperties")),
            )

        overlay_last_to_first = _overlay_counts(top_layers, range(0, layer_index))
        overlay_first_to_last = _overlay_counts(top_layers, range(layer_index + 1, len(top_layers)))
        self_has_matte = layer.get("tt") is not None or layer.get("td") is not None
        self_has_mask = _layer_has_mask(layer)

        logger.info(
            (
                "Text layer stack check path=%s layer=%s layer_index=%s "
                "assumption=last_to_first overlay_render=%s overlay_shape=%s overlay_solid=%s overlay_matte=%s overlay_mask=%s"
            ),
            path,
            display_name,
            layer_index,
            overlay_last_to_first["render"],
            overlay_last_to_first["shape"],
            overlay_last_to_first["solid"],
            overlay_last_to_first["matte"],
            overlay_last_to_first["mask"],
        )
        logger.info(
            (
                "Text layer stack check path=%s layer=%s layer_index=%s "
                "assumption=first_to_last overlay_render=%s overlay_shape=%s overlay_solid=%s overlay_matte=%s overlay_mask=%s"
            ),
            path,
            display_name,
            layer_index,
            overlay_first_to_last["render"],
            overlay_first_to_last["shape"],
            overlay_first_to_last["solid"],
            overlay_first_to_last["matte"],
            overlay_first_to_last["mask"],
        )

        logger.info(
            (
                "Text layer matte/mask self-check path=%s layer=%s self_matte=%s self_mask=%s "
                "under_solid(last_to_first)=%s under_matte(last_to_first)=%s under_mask(last_to_first)=%s"
            ),
            path,
            display_name,
            self_has_matte,
            self_has_mask,
            overlay_last_to_first["solid"] > 0,
            overlay_last_to_first["matte"] > 0,
            overlay_last_to_first["mask"] > 0,
        )

        if (
            overlay_last_to_first["shape"] > 0
            or overlay_last_to_first["solid"] > 0
            or overlay_last_to_first["matte"] > 0
            or overlay_last_to_first["mask"] > 0
        ):
            logger.warning(
                (
                    "Text layer may be occluded path=%s layer=%s layer_index=%s "
                    "reason=overlay_layers(last_to_first) shape=%s solid=%s matte=%s mask=%s"
                ),
                path,
                display_name,
                layer_index,
                overlay_last_to_first["shape"],
                overlay_last_to_first["solid"],
                overlay_last_to_first["matte"],
                overlay_last_to_first["mask"],
            )
        else:
            logger.info(
                "Text layer occlusion risk low path=%s layer=%s layer_index=%s",
                path,
                display_name,
                layer_index,
            )


def move_text_layer_to_top(
    data: dict[str, Any],
    layer_name: str = TARGET_TEXT_LAYER_NAME,
    logger: logging.Logger | None = None,
) -> bool:
    active_logger = logger or logging.getLogger(__name__)
    if _is_glyph_bank_layer(layer_name):
        active_logger.info(
            "Skipped glyph_bank in move_text_layer_to_top layer_name=%s reason=glyph_bank_protected",
            layer_name,
        )
        return False

    layers = data.get("layers")
    if not isinstance(layers, list):
        active_logger.warning(
            "Move text layer to top skipped reason=no_layers_array layer_name=%s",
            layer_name,
        )
        return False

    target_name_norm = _normalize_name(layer_name)
    found_index: int | None = None
    found_layer: dict[str, Any] | None = None

    for index, candidate in enumerate(layers):
        if not isinstance(candidate, dict):
            continue
        candidate_name = _normalize_name(str(candidate.get("nm", "")))
        if candidate_name != target_name_norm:
            continue
        if candidate.get("ty") != 5:
            continue
        found_index = index
        found_layer = candidate
        break

    if found_index is None or found_layer is None:
        active_logger.warning(
            "Move text layer to top skipped reason=layer_not_found layer_name=%s",
            layer_name,
        )
        return False

    if found_index == len(layers) - 1:
        active_logger.info(
            "Moved target text layer to top skipped reason=already_top layer=%s layer_index=%s ind=%s",
            layer_name,
            found_index,
            found_layer.get("ind"),
        )
        return False

    old_index = found_index
    old_ind = found_layer.get("ind")
    extracted = layers.pop(found_index)
    layers.append(extracted)
    new_index = len(layers) - 1

    tail_preview: list[str] = []
    tail_start = max(0, len(layers) - 5)
    for idx in range(tail_start, len(layers)):
        tail_layer = layers[idx]
        if not isinstance(tail_layer, dict):
            tail_preview.append(f"{idx}:<invalid>")
            continue
        tail_preview.append(
            f"{idx}:{tail_layer.get('nm')}|ty={tail_layer.get('ty')}|ind={tail_layer.get('ind')}"
        )

    active_logger.info(
        (
            "Moved target text layer to top layer=%s ind=%s old_index=%s new_index=%s "
            "total_layers=%s tail=%s"
        ),
        layer_name,
        old_ind,
        old_index,
        new_index,
        len(layers),
        tail_preview,
    )
    return True


def remove_glyph_bank_layers(
    data: dict[str, Any],
    logger: logging.Logger | None = None,
) -> int:
    active_logger = logger or logging.getLogger(__name__)
    layers = data.get("layers")
    if not isinstance(layers, list):
        active_logger.warning(
            "glyph_bank layers removed count=0 reason=no_layers_array"
        )
        return 0

    removed: list[dict[str, Any]] = []
    filtered_layers: list[Any] = []
    for index, layer in enumerate(layers):
        if isinstance(layer, dict):
            layer_name = str(layer.get("nm", "")).strip()
            if _is_glyph_bank_layer(layer_name):
                removed.append(
                    {
                        "index": index,
                        "nm": layer_name,
                        "ty": layer.get("ty"),
                        "ind": layer.get("ind"),
                    }
                )
                continue
        filtered_layers.append(layer)

    if removed:
        data["layers"] = filtered_layers
        active_logger.info(
            "glyph_bank layers removed count=%s removed=%s",
            len(removed),
            removed,
        )
        return len(removed)

    active_logger.info("glyph_bank layers removed count=0")
    return 0


def _bg_match_decision(name: str, markers: tuple[str, ...]) -> BgDecision:
    if not name:
        return BgDecision()

    normalized = _normalize_name(name)
    for marker in markers:
        marker_norm = _normalize_name(marker)
        if not marker_norm:
            continue

        if marker_norm == "bg":
            if _TOKEN_BG_RE.search(normalized):
                return BgDecision(True, "marker:bg_token", True)
            continue

        if marker_norm == "background":
            if "background" in normalized:
                return BgDecision(True, "marker:background_substring", True)
            continue

        if marker_norm == "фон":
            if _TOKEN_FON_RE.search(normalized):
                return BgDecision(True, "marker:фон_token", True)
            continue

        if marker_norm == "фигура 1":
            if _FIGURA1_RE.search(normalized):
                return BgDecision(True, "marker:фигура1_exact", True)
            continue

        if marker_norm == "solid":
            if _TOKEN_SOLID_RE.search(normalized):
                # weak marker: only marks current node itself; does not open inherited bg-scope
                return BgDecision(True, "marker:solid_token", False)
            continue

        if len(marker_norm) <= 3:
            token_re = re.compile(
                rf"(?<![a-z0-9а-яё]){re.escape(marker_norm)}(?![a-z0-9а-яё])",
                re.IGNORECASE,
            )
            if token_re.search(normalized):
                return BgDecision(True, f"marker:{marker_norm}_token", True)
            continue

        if marker_norm in normalized:
            return BgDecision(True, f"marker:{marker_norm}_substring", True)

    return BgDecision()


def _is_scope_container(node: dict[str, Any]) -> bool:
    if any(key in node for key in ("layers", "shapes", "it", "assets")):
        return True
    node_type = node.get("ty")
    if isinstance(node_type, str):
        return node_type in {"gr", "comp"}
    if isinstance(node_type, int):
        return node_type in {0, 1, 2, 3, 4, 5}
    return False


def _walk_lottie(node: Any, path: str = "$"):
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk_lottie(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk_lottie(value, f"{path}[{index}]")


def _apply_color_recursive(
    value: Any,
    rgba: list[float],
    path: str,
) -> tuple[int, bool]:
    updated_arrays = 0
    recognized_structure = False

    if isinstance(value, list):
        if _looks_like_color_array(value):
            _set_color_array(value, rgba)
            return 1, True
        for index, item in enumerate(value):
            changed, recognized = _apply_color_recursive(item, rgba, f"{path}[{index}]")
            updated_arrays += changed
            recognized_structure = recognized_structure or recognized
        return updated_arrays, recognized_structure

    if isinstance(value, dict):
        traversed_known_key = False
        for key in ("k", "s", "e"):
            if key in value:
                traversed_known_key = True
                changed, recognized = _apply_color_recursive(
                    value[key], rgba, f"{path}.{key}"
                )
                updated_arrays += changed
                recognized_structure = recognized_structure or recognized
        if not traversed_known_key:
            for key, nested in value.items():
                if isinstance(nested, (dict, list)):
                    changed, recognized = _apply_color_recursive(
                        nested, rgba, f"{path}.{key}"
                    )
                    updated_arrays += changed
                    recognized_structure = recognized_structure or recognized
        return updated_arrays, recognized_structure or traversed_known_key

    return 0, False


def replace_text_in_lottie(
    data: dict[str, Any],
    new_text: str,
    target_layer_names: set[str] | None = None,
    force_text_position: bool = True,
    text_position_override: list[float] | None = None,
    text_box_config: TextBoxConfig | None = None,
    force_min_text_size: float | None = None,
    min_visible_text_size_warning: float = 20.0,
    text_debug_mode: bool = True,
    template_name: str | None = None,
    logger: logging.Logger | None = None,
) -> LottieProcessingStats:
    active_logger = logger or logging.getLogger(__name__)
    stats = LottieProcessingStats()
    template_name_value = (template_name or str(data.get("__template_name__", ""))).strip()
    autofit_disabled_for_template = template_name_value.lower() == _EMOJI3_TEMPLATE_FILE
    autofit_shrink_disabled_for_template = template_name_value.lower() == _EMOJI4_TEMPLATE_FILE
    fixed_font_size_for_template: float | None = None
    if template_name_value.lower() == _EMOJI6_TEMPLATE_FILE:
        fixed_font_size_for_template = _EMOJI6_FIXED_FONT_SIZE
    elif template_name_value.lower() == _EMOJI13_TEMPLATE_FILE:
        fixed_font_size_for_template = _EMOJI13_FIXED_FONT_SIZE
    elif template_name_value.lower() == _EMOJI14_TEMPLATE_FILE:
        fixed_font_size_for_template = _EMOJI14_FIXED_FONT_SIZE
    elif template_name_value.lower() == _EMOJI15_TEMPLATE_FILE:
        fixed_font_size_for_template = _EMOJI15_FIXED_FONT_SIZE
    elif template_name_value.lower() == _EMOJI16_TEMPLATE_FILE:
        fixed_font_size_for_template = _EMOJI16_FIXED_FONT_SIZE
    elif template_name_value.lower() == _EMOJI8_TEMPLATE_FILE:
        fixed_font_size_for_template = _EMOJI8_FIXED_FONT_SIZE
    elif template_name_value.lower() == _EMOJI8_NESTED_TEXT_TEMPLATE_FILE:
        fixed_font_size_for_template = _EMOJI8_NESTED_FIXED_FONT_SIZE
    elif template_name_value.lower() == _EMOJI17_TEMPLATE_FILE:
        fixed_font_size_for_template = _EMOJI17_FIXED_FONT_SIZE
    elif template_name_value.lower() == _EMOJI18_TEMPLATE_FILE:
        fixed_font_size_for_template = _EMOJI18_FIXED_FONT_SIZE
    elif template_name_value.lower() == _EMOJI20_TEMPLATE_FILE:
        fixed_font_size_for_template = _EMOJI20_FIXED_FONT_SIZE
    target_names = {name.lower() for name in (target_layer_names or set())}
    comp_width = _as_float(data.get("w"))
    comp_height = _as_float(data.get("h"))
    top_layers = data.get("layers") if isinstance(data.get("layers"), list) else []
    layers_by_ind: dict[int, tuple[int, dict[str, Any]]] = {}
    for index, layer in enumerate(top_layers):
        if not isinstance(layer, dict):
            continue
        layer_ind = _as_int(layer.get("ind"))
        if layer_ind is None:
            continue
        layers_by_ind[layer_ind] = (index, layer)

    for path, node in _walk_lottie(data):
        if not isinstance(node, dict):
            continue
        text_container = node.get("t")
        if not isinstance(text_container, dict):
            continue

        layer_name = str(node.get("nm", "")).strip()
        if _is_glyph_bank_layer(layer_name):
            active_logger.info(
                "Skipped glyph_bank in text replacement path=%s layer=%s reason=glyph_bank_protected",
                path,
                layer_name or "<unnamed>",
            )
            continue
        layer_name_lc = layer_name.lower()
        if target_names and layer_name_lc not in target_names:
            continue

        keyframes = text_container.get("d", {}).get("k")
        if not isinstance(keyframes, list):
            continue

        layer_index = _resolve_layer_index(path, node, top_layers)
        if text_debug_mode:
            _log_text_layer_diagnostics(
                logger=active_logger,
                path=path,
                layer=node,
                layer_name=layer_name,
                layer_index=layer_index,
                top_layers=top_layers,
                layers_by_ind=layers_by_ind,
            )

        ks = node.get("ks") if isinstance(node.get("ks"), dict) else {}
        layer_position = _extract_animatable_value(ks.get("p"))
        layer_scale = _extract_animatable_value(ks.get("s"))
        layer_anchor = _extract_animatable_value(ks.get("a"))
        if text_debug_mode:
            active_logger.info(
                "Text layer transform path=%s layer=%s ks.p=%s ks.s=%s ks.a=%s",
                path,
                layer_name or "<unnamed>",
                _serialize_for_log(layer_position),
                _serialize_for_log(layer_scale),
                _serialize_for_log(layer_anchor),
            )

        layer_position_xyz = _as_xyz(layer_position)
        applied_position_override = False
        position_override_reason: str | None = None
        position_before_override = copy.deepcopy(layer_position)

        if force_text_position and isinstance(ks, dict) and "p" in ks:
            desired_position: list[float] | None = None
            current_z = layer_position_xyz[2] if layer_position_xyz else 0.0

            if text_position_override and len(text_position_override) >= 2:
                override_x = _as_float(text_position_override[0])
                override_y = _as_float(text_position_override[1])
                override_z = _as_float(text_position_override[2]) if len(text_position_override) >= 3 else current_z
                if override_x is not None and override_y is not None:
                    desired_position = [override_x, override_y, override_z if override_z is not None else current_z]
                    position_override_reason = "explicit_override"

            if desired_position is not None:
                changed, mode = _apply_position_override(ks.get("p"), desired_position)
                new_position = _extract_animatable_value(ks.get("p"))
                if changed:
                    applied_position_override = True
                    active_logger.info(
                        "Text position override applied path=%s layer=%s reason=%s mode=%s old_ks.p=%s new_ks.p=%s",
                        path,
                        layer_name or "<unnamed>",
                        position_override_reason,
                        mode,
                        _serialize_for_log(position_before_override),
                        _serialize_for_log(new_position),
                    )
                else:
                    active_logger.warning(
                        "Text position override requested but not applied path=%s layer=%s reason=%s mode=%s current_ks.p=%s",
                        path,
                        layer_name or "<unnamed>",
                        position_override_reason,
                        mode,
                        _serialize_for_log(new_position),
                    )
            else:
                parent_value = node.get("parent")
                if parent_value in (None, 0):
                    active_logger.info(
                        "Text position preserved path=%s layer=%s reason=no_parent_keep_template_position ks.p=%s",
                        path,
                        layer_name or "<unnamed>",
                        _serialize_for_log(_extract_animatable_value(ks.get("p"))),
                    )
                else:
                    active_logger.info(
                        "Text position unchanged path=%s layer=%s reason=no_explicit_override parent=%s ks.p=%s",
                        path,
                        layer_name or "<unnamed>",
                        parent_value,
                        _serialize_for_log(_extract_animatable_value(ks.get("p"))),
                    )

        pos_xy = _as_xy(_extract_animatable_value(ks.get("p")))
        if pos_xy and comp_width is not None and comp_height is not None:
            px, py = pos_xy
            if px < -(0.5 * comp_width) or px > (1.5 * comp_width) or py < -(0.5 * comp_height) or py > (1.5 * comp_height):
                stats.text_visibility_warnings += 1
                active_logger.warning(
                    "Text layer position may be out of viewport path=%s layer=%s p=%s comp_size=[%s,%s]",
                    path,
                    layer_name or "<unnamed>",
                    _serialize_for_log(_extract_animatable_value(ks.get("p"))),
                    comp_width,
                    comp_height,
                )

        layer_had_text = False
        final_text_value: str | None = None
        for index, keyframe in enumerate(keyframes):
            if not isinstance(keyframe, dict):
                continue
            style = keyframe.get("s")
            if not isinstance(style, dict):
                continue
            if "t" not in style:
                continue

            stats.text_keyframes_found += 1
            old_text = style.get("t")
            if old_text != new_text:
                style["t"] = new_text
                stats.text_keyframes_updated += 1
            final_text_value = style.get("t")

            style_path = f"{path}.t.d.k[{index}].s"
            effective_text_box = text_box_config or _default_text_box_for_layer(layer_name)
            source_text_size = _as_float(style.get("s"))
            if (
                effective_text_box is not None
                and not autofit_disabled_for_template
                and not autofit_shrink_disabled_for_template
            ):
                _apply_text_box_layout(
                    style=style,
                    new_text=new_text,
                    text_box_config=effective_text_box,
                    path=style_path,
                    logger=active_logger,
                )
            elif effective_text_box is not None and autofit_shrink_disabled_for_template:
                computed_autofit_size, _computed_tracking, _estimated_width, _max_word_len, _word_penalty_px = _compute_text_box_layout_values(
                    new_text=new_text,
                    text_box_config=effective_text_box,
                    old_tracking=_as_float(style.get("tr")),
                )
                if source_text_size is not None:
                    style["s"] = round(source_text_size * _EMOJI4_FONT_SIZE_MULTIPLIER, 6)
                text_len_for_template = _text_len_for_fit(str(style.get("t", new_text)))
                if template_name_value.lower() == _EMOJI4_TEMPLATE_FILE and text_len_for_template > 4:
                    previous_size = _as_float(style.get("s"))
                    extra_shrink_px = 1.0 + max(0, text_len_for_template - 5) * 0.75
                    style["s"] = round(
                        max(float(effective_text_box.min_font_size), float(style["s"]) - extra_shrink_px),
                        6,
                    )
                    active_logger.info(
                        "Template long-text shrink applied template_name=%s text_len=%s old_size=%s final_font_size=%s",
                        template_name_value or None,
                        text_len_for_template,
                        previous_size,
                        _as_float(style.get("s")),
                    )
                final_font_size = _as_float(style.get("s"))
                active_logger.info(
                    "Text auto-fit shrink disabled template_name=%s old_size=%s computed_autofit_size=%s final_font_size=%s autofit_shrink_disabled=%s",
                    template_name_value or None,
                    source_text_size,
                    computed_autofit_size,
                    final_font_size,
                    True,
                )
            elif effective_text_box is not None and autofit_disabled_for_template:
                active_logger.info(
                    "Text auto-fit template override template_name=%s source_text_size=%s autofit_disabled_for_template=%s final_font_size=%s",
                    template_name_value or None,
                    source_text_size,
                    True,
                    _as_float(style.get("s")),
                )
            if fixed_font_size_for_template is not None:
                style["s"] = round(float(fixed_font_size_for_template), 6)
                text_len_for_template = _text_len_for_fit(str(style.get("t", new_text)))
                if template_name_value.lower() == _EMOJI8_TEMPLATE_FILE and text_len_for_template > 4:
                    previous_size = _as_float(style.get("s"))
                    extra_shrink_px = 6.0 + max(0, text_len_for_template - 5) * 3.0
                    style["s"] = round(
                        max(18.0, float(style["s"]) - extra_shrink_px),
                        6,
                    )
                    active_logger.info(
                        "Template long-text shrink applied template_name=%s text_len=%s old_size=%s final_font_size=%s",
                        template_name_value or None,
                        text_len_for_template,
                        previous_size,
                        _as_float(style.get("s")),
                    )
                active_logger.info(
                    "Text auto-fit template fixed size template_name=%s old_size=%s final_font_size=%s",
                    template_name_value or None,
                    source_text_size,
                    _as_float(style.get("s")),
                )
            if template_name_value.lower() == _EMOJI9_TEMPLATE_FILE:
                emoji9_old_size = _as_float(style.get("s"))
                if emoji9_old_size is not None:
                    style["s"] = round(max(10.0, emoji9_old_size - _EMOJI9_TEXT_SIZE_DELTA_PX), 6)
                    active_logger.info(
                        "Template font size tweak template_name=%s old_size=%s final_font_size=%s",
                        template_name_value or None,
                        emoji9_old_size,
                        _as_float(style.get("s")),
                    )
            if template_name_value.lower() == _EMOJI10_TEMPLATE_FILE:
                emoji10_old_size = _as_float(style.get("s"))
                if emoji10_old_size is not None:
                    emoji10_new_size = max(10.0, (emoji10_old_size * _EMOJI10_TEXT_SIZE_MULTIPLIER) - _EMOJI10_TEXT_SIZE_DELTA_PX)
                    text_len_for_template = _text_len_for_fit(str(style.get("t", new_text)))
                    if text_len_for_template > 4:
                        emoji10_extra_shrink = _EMOJI10_LONG_TEXT_SHRINK_BASE_PX + max(0, text_len_for_template - 5) * _EMOJI10_LONG_TEXT_SHRINK_STEP_PX
                        emoji10_new_size = max(10.0, emoji10_new_size - emoji10_extra_shrink)
                        active_logger.info(
                            "Template long-text shrink applied template_name=%s text_len=%s extra_shrink_px=%s",
                            template_name_value or None,
                            text_len_for_template,
                            round(emoji10_extra_shrink, 6),
                        )
                    style["s"] = round(emoji10_new_size, 6)
                    active_logger.info(
                        "Template font size tweak template_name=%s old_size=%s final_font_size=%s",
                        template_name_value or None,
                        emoji10_old_size,
                        _as_float(style.get("s")),
                    )
            style_sz = style.get("sz")
            style_ps = style.get("ps")
            style_lh = style.get("lh")
            style_ls = style.get("ls")
            style_j = style.get("j")
            style_tr = style.get("tr")
            style_size = _as_float(style.get("s"))
            stats.text_layout_keyframes_logged += 1

            if text_debug_mode:
                active_logger.info(
                    "Text style path=%s sz=%s ps=%s lh=%s ls=%s j=%s tr=%s final_text=%r",
                    style_path,
                    _serialize_for_log(style_sz),
                    _serialize_for_log(style_ps),
                    style_lh,
                    style_ls,
                    style_j,
                    style_tr,
                    style.get("t"),
                )

            if style_sz is not None or style_ps is not None:
                if text_debug_mode:
                    active_logger.info(
                        "Text paragraph box path=%s sz=%s ps=%s",
                        style_path,
                        _serialize_for_log(style_sz),
                        _serialize_for_log(style_ps),
                    )

            if style_size is not None:
                if style_size < min_visible_text_size_warning:
                    stats.text_visibility_warnings += 1
                    active_logger.warning(
                        "Text font size may be too small path=%s size=%s threshold=%s",
                        style_path,
                        style_size,
                        min_visible_text_size_warning,
                    )
                if force_min_text_size is not None and style_size < force_min_text_size:
                    old_size = style_size
                    style["s"] = force_min_text_size
                    stats.text_size_forced += 1
                    active_logger.info(
                        "Text font size forced path=%s old=%s new=%s",
                        style_path,
                        old_size,
                        force_min_text_size,
                    )

            box_xy = _as_xy(style_sz)
            if box_xy:
                box_w, box_h = box_xy
                if box_w <= 1 or box_h <= 1:
                    stats.text_visibility_warnings += 1
                    active_logger.warning(
                        "Text clipping box is too small path=%s sz=%s",
                        style_path,
                        _serialize_for_log(style_sz),
                    )
                if style_size is not None and box_h > 0 and style_size > (box_h * 1.1):
                    stats.text_visibility_warnings += 1
                    active_logger.warning(
                        "Text may be vertically clipped path=%s font_size=%s box_h=%s",
                        style_path,
                        style_size,
                        box_h,
                    )
                if style_size is not None and isinstance(style.get("t"), str) and box_w > 0:
                    estimated_width = max(1, len(style.get("t"))) * style_size * 0.55
                    if estimated_width > (box_w * 1.1):
                        stats.text_visibility_warnings += 1
                        active_logger.warning(
                            "Text may be horizontally clipped path=%s estimated_width=%s box_w=%s",
                            style_path,
                            round(estimated_width, 2),
                            box_w,
                        )

            paragraph_xy = _as_xy(style_ps)
            if paragraph_xy and comp_width is not None and comp_height is not None:
                ps_x, ps_y = paragraph_xy
                if abs(ps_x) > comp_width or abs(ps_y) > comp_height:
                    stats.text_visibility_warnings += 1
                    active_logger.warning(
                        "Text paragraph offset is large path=%s ps=%s comp_size=[%s,%s]",
                        style_path,
                        _serialize_for_log(style_ps),
                        comp_width,
                        comp_height,
                    )

            layer_had_text = True
            active_logger.info(
                "Text keyframe updated path=%s layer=%s keyframe=%s old=%r new=%r",
                f"{path}.t.d.k[{index}].s.t",
                layer_name or "<unnamed>",
                index,
                old_text,
                new_text,
            )

        if layer_had_text:
            stats.text_layers_found += 1
            active_logger.info("Text layer found path=%s layer=%s", path, layer_name or "<unnamed>")
            if text_debug_mode:
                active_logger.info(
                    "Text layer debug path=%s layer=%s final_text=%r ks.p=%s ks.a=%s ks.s=%s applied_override=%s",
                    path,
                    layer_name or "<unnamed>",
                    final_text_value,
                    _serialize_for_log(_extract_animatable_value(ks.get("p"))),
                    _serialize_for_log(_extract_animatable_value(ks.get("a"))),
                    _serialize_for_log(_extract_animatable_value(ks.get("s"))),
                    applied_position_override,
                )

    move_text_layer_to_top(
        data=data,
        layer_name=TARGET_TEXT_LAYER_NAME,
        logger=active_logger,
    )

    active_logger.info(
        (
            "Text replacement done layers_found=%s keyframes_found=%s keyframes_updated=%s "
            "layout_logged=%s size_forced=%s visibility_warnings=%s"
        ),
        stats.text_layers_found,
        stats.text_keyframes_found,
        stats.text_keyframes_updated,
        stats.text_layout_keyframes_logged,
        stats.text_size_forced,
        stats.text_visibility_warnings,
    )
    return stats


def update_text_layer_colors(
    data: dict[str, Any],
    text_fill_hex: str,
    text_stroke_hex: str | None = None,
    logger: logging.Logger | None = None,
) -> LottieProcessingStats:
    active_logger = logger or logging.getLogger(__name__)
    stats = LottieProcessingStats()
    fill_rgba = hex_to_rgba(text_fill_hex)
    stroke_rgba = hex_to_rgba(text_stroke_hex) if text_stroke_hex else None

    keyframes_total = 0
    keyframes_with_color_update = 0

    active_logger.info(
        "Text color update start fill=%s stroke=%s",
        text_fill_hex,
        text_stroke_hex,
    )

    for path, node in _walk_lottie(data):
        if not isinstance(node, dict):
            continue

        text_container = node.get("t")
        if not isinstance(text_container, dict):
            continue

        keyframes = text_container.get("d", {}).get("k")
        if not isinstance(keyframes, list):
            continue

        layer_name_raw = str(node.get("nm", "")).strip()
        if _is_glyph_bank_layer(layer_name_raw):
            active_logger.info(
                "Skipped glyph_bank in text color update path=%s layer=%s reason=glyph_bank_protected",
                path,
                layer_name_raw or "<unnamed>",
            )
            continue
        layer_name = layer_name_raw or "<unnamed>"
        active_logger.info("Text color layer path=%s layer=%s", path, layer_name)

        for index, keyframe in enumerate(keyframes):
            if not isinstance(keyframe, dict):
                continue
            style = keyframe.get("s")
            if not isinstance(style, dict):
                continue

            keyframes_total += 1
            keyframe_color_changed = False

            fc_path = f"{path}.t.d.k[{index}].s.fc"
            if "fc" in style:
                stats.text_fill_colors_found += 1
                old_fc = copy.deepcopy(style["fc"])
                changed_fc, recognized_fc = _apply_color_recursive(style["fc"], fill_rgba, fc_path)
                if changed_fc > 0:
                    stats.text_fill_colors_updated += changed_fc
                    stats.color_arrays_updated += changed_fc
                    keyframe_color_changed = True
                    active_logger.info(
                        "Text color fc updated path=%s old=%s new=%s arrays_updated=%s",
                        fc_path,
                        _serialize_for_log(old_fc),
                        _serialize_for_log(style["fc"]),
                        changed_fc,
                    )
                else:
                    reason = "unrecognized text fill color structure" if not recognized_fc else "text fill color unchanged"
                    _record_skipped(stats=stats, logger=active_logger, path=fc_path, reason=reason)
            else:
                active_logger.warning("Text color fc missing path=%s layer=%s", fc_path, layer_name)

            if stroke_rgba is not None:
                sc_path = f"{path}.t.d.k[{index}].s.sc"
                if "sc" in style:
                    stats.text_stroke_colors_found += 1
                    old_sc = copy.deepcopy(style["sc"])
                    changed_sc, recognized_sc = _apply_color_recursive(style["sc"], stroke_rgba, sc_path)
                    if changed_sc > 0:
                        stats.text_stroke_colors_updated += changed_sc
                        stats.color_arrays_updated += changed_sc
                        keyframe_color_changed = True
                        active_logger.info(
                            "Text color sc updated path=%s old=%s new=%s arrays_updated=%s",
                            sc_path,
                            _serialize_for_log(old_sc),
                            _serialize_for_log(style["sc"]),
                            changed_sc,
                        )
                    else:
                        reason = "unrecognized text stroke color structure" if not recognized_sc else "text stroke color unchanged"
                        _record_skipped(stats=stats, logger=active_logger, path=sc_path, reason=reason)
                else:
                    active_logger.warning("Text color sc missing path=%s layer=%s", sc_path, layer_name)

            if keyframe_color_changed:
                keyframes_with_color_update += 1

    active_logger.info(
        "Text color update done keyframes_total=%s keyframes_updated=%s fc=%s/%s sc=%s/%s arrays_updated=%s skipped=%s",
        keyframes_total,
        keyframes_with_color_update,
        stats.text_fill_colors_updated,
        stats.text_fill_colors_found,
        stats.text_stroke_colors_updated,
        stats.text_stroke_colors_found,
        stats.color_arrays_updated,
        stats.skipped_color_nodes,
    )
    return stats


def recolor_lottie(
    data: dict[str, Any],
    stroke_hex: str,
    elements_hex: str,
    bg_markers: tuple[str, ...] | None = None,
    logger: logging.Logger | None = None,
) -> LottieProcessingStats:
    active_logger = logger or logging.getLogger(__name__)
    stats = LottieProcessingStats()
    effective_markers = tuple(_normalize_name(marker) for marker in (bg_markers or DEFAULT_BG_MARKERS))
    stroke_rgba = hex_to_rgba(stroke_hex)
    elements_rgba = hex_to_rgba(elements_hex)
    background_rgba = [0.0, 0.0, 0.0, 1.0]

    def recolor_text_keyframes(
        node: dict[str, Any],
        node_path: str,
        current_is_bg: bool,
        container_name: str,
    ) -> None:
        text_container = node.get("t")
        if not isinstance(text_container, dict):
            return
        keyframes = text_container.get("d", {}).get("k")
        if not isinstance(keyframes, list):
            return
        layer_name = str(node.get("nm", "")).strip()
        if _is_glyph_bank_layer(layer_name):
            active_logger.info(
                "Skipped glyph_bank in recolor text stage path=%s layer=%s reason=glyph_bank_protected",
                node_path,
                layer_name or "<unnamed>",
            )
            return

        fill_target = background_rgba if current_is_bg else elements_rgba
        fill_target_name = "background_black" if current_is_bg else "elements_color"
        for index, keyframe in enumerate(keyframes):
            if not isinstance(keyframe, dict):
                continue
            style = keyframe.get("s")
            if not isinstance(style, dict):
                continue

            if "fc" in style:
                stats.text_fill_colors_found += 1
                fc_path = f"{node_path}.t.d.k[{index}].s.fc"
                changed, recognized = _apply_color_recursive(
                    style["fc"],
                    fill_target,
                    fc_path,
                )
                if changed > 0:
                    stats.text_fill_colors_updated += changed
                    stats.color_arrays_updated += changed
                    active_logger.info(
                        "Text fc recolored path=%s container=%s bg_branch=%s applied_color=%s arrays_updated=%s",
                        fc_path,
                        container_name,
                        current_is_bg,
                        fill_target_name,
                        changed,
                    )
                else:
                    reason = "unrecognized text fill color structure" if not recognized else "text fill color unchanged"
                    _record_skipped(
                        stats=stats,
                        logger=active_logger,
                        path=fc_path,
                        reason=reason,
                    )

            if "sc" in style:
                stats.text_stroke_colors_found += 1
                sc_path = f"{node_path}.t.d.k[{index}].s.sc"
                changed, recognized = _apply_color_recursive(
                    style["sc"],
                    stroke_rgba,
                    sc_path,
                )
                if changed > 0:
                    stats.text_stroke_colors_updated += changed
                    stats.color_arrays_updated += changed
                    active_logger.info(
                        "Text sc recolored path=%s container=%s applied_color=stroke_color arrays_updated=%s",
                        sc_path,
                        container_name,
                        changed,
                    )
                else:
                    reason = "unrecognized text stroke color structure" if not recognized else "text stroke color unchanged"
                    _record_skipped(
                        stats=stats,
                        logger=active_logger,
                        path=sc_path,
                        reason=reason,
                    )

    def recolor_shape_node(
        node: dict[str, Any],
        node_path: str,
        current_is_bg: bool,
        container_name: str,
    ) -> None:
        node_type = node.get("ty")
        if node_type not in ("fl", "st"):
            return

        node_name = str(node.get("nm", "")).strip()

        if node_type == "fl":
            stats.fill_nodes_found += 1
            target_rgba = background_rgba if current_is_bg else elements_rgba
            target_name = "background_black" if current_is_bg else "elements_color"
            target_path = f"{node_path}.c"
            changed, recognized = _apply_color_recursive(node.get("c"), target_rgba, target_path)
            if changed > 0:
                stats.fill_nodes_recolored += 1
                stats.color_arrays_updated += changed
                active_logger.info(
                    "Fill recolored path=%s nm=%s container=%s bg_branch=%s applied_color=%s arrays_updated=%s",
                    node_path,
                    node_name or "<unnamed>",
                    container_name,
                    current_is_bg,
                    target_name,
                    changed,
                )
            else:
                reason = "unrecognized fill color structure" if not recognized else "fill color unchanged"
                _record_skipped(stats=stats, logger=active_logger, path=target_path, reason=reason)
            return

        stats.stroke_nodes_found += 1
        target_path = f"{node_path}.c"
        changed, recognized = _apply_color_recursive(node.get("c"), stroke_rgba, target_path)
        if changed > 0:
            stats.stroke_nodes_recolored += 1
            stats.color_arrays_updated += changed
            active_logger.info(
                "Stroke recolored path=%s nm=%s container=%s applied_color=stroke_color arrays_updated=%s",
                node_path,
                node_name or "<unnamed>",
                container_name,
                changed,
            )
        else:
            reason = "unrecognized stroke color structure" if not recognized else "stroke color unchanged"
            _record_skipped(stats=stats, logger=active_logger, path=target_path, reason=reason)

    def walk(
        node: Any,
        path: str = "$",
        bg_scope_active: bool = False,
        bg_scope_reason: str = "none",
        bg_scope_origin: str = "$",
        container_name: str = "<root>",
    ) -> None:
        if isinstance(node, dict):
            node_name = str(node.get("nm", "")).strip()
            effective_container_name = node_name or container_name
            node_type = node.get("ty")

            self_bg = _bg_match_decision(node_name, effective_markers)
            parent_is_bg = bg_scope_active
            current_is_bg = self_bg.is_bg or parent_is_bg

            if self_bg.is_bg:
                bg_reason = f"self:{self_bg.reason}"
            elif parent_is_bg:
                bg_reason = f"inherited:{bg_scope_reason} from {bg_scope_origin}"
            else:
                bg_reason = "none"

            if node_name or self_bg.is_bg or parent_is_bg or node_type in ("fl", "st"):
                active_logger.info(
                    "BG decision path=%s nm=%s parent_is_bg=%s current_is_bg=%s reason=%s strong_marker=%s node_type=%r",
                    path,
                    node_name or "<unnamed>",
                    parent_is_bg,
                    current_is_bg,
                    bg_reason,
                    self_bg.strong,
                    node_type,
                )

            if self_bg.is_bg and self_bg.strong and _is_scope_container(node):
                next_bg_scope_active = True
                next_bg_scope_reason = self_bg.reason or "self"
                next_bg_scope_origin = path
            elif parent_is_bg and _is_scope_container(node):
                next_bg_scope_active = True
                next_bg_scope_reason = bg_scope_reason
                next_bg_scope_origin = bg_scope_origin
            else:
                next_bg_scope_active = False
                next_bg_scope_reason = "none"
                next_bg_scope_origin = path

            recolor_text_keyframes(
                node=node,
                node_path=path,
                current_is_bg=current_is_bg,
                container_name=effective_container_name,
            )
            recolor_shape_node(
                node=node,
                node_path=path,
                current_is_bg=current_is_bg,
                container_name=effective_container_name,
            )

            for key, value in node.items():
                walk(
                    node=value,
                    path=f"{path}.{key}",
                    bg_scope_active=next_bg_scope_active,
                    bg_scope_reason=next_bg_scope_reason,
                    bg_scope_origin=next_bg_scope_origin,
                    container_name=effective_container_name,
                )
            return

        if isinstance(node, list):
            for index, value in enumerate(node):
                walk(
                    node=value,
                    path=f"{path}[{index}]",
                    bg_scope_active=bg_scope_active,
                    bg_scope_reason=bg_scope_reason,
                    bg_scope_origin=bg_scope_origin,
                    container_name=container_name,
                )

    walk(data)
    active_logger.info(
        "Recolor done fills=%s/%s strokes=%s/%s text_fc=%s/%s text_sc=%s/%s arrays_updated=%s skipped=%s",
        stats.fill_nodes_recolored,
        stats.fill_nodes_found,
        stats.stroke_nodes_recolored,
        stats.stroke_nodes_found,
        stats.text_fill_colors_updated,
        stats.text_fill_colors_found,
        stats.text_stroke_colors_updated,
        stats.text_stroke_colors_found,
        stats.color_arrays_updated,
        stats.skipped_color_nodes,
    )
    if stats.stroke_nodes_found == 0:
        active_logger.info(
            "No stroke nodes found in template. This is valid when source JSON has no ty=st nodes."
        )
    return stats


def build_tgs_bytes(data: dict[str, Any], logger: logging.Logger | None = None) -> bytes:
    global _LAST_X_RENDER_MARKER
    active_logger = logger or logging.getLogger(__name__)
    layers = data.get("layers")
    layers_count = len(layers) if isinstance(layers, list) else 0
    glyph_bank_exists_before_build = bool(
        isinstance(layers, list)
        and any(
            isinstance(layer, dict)
            and _is_glyph_bank_layer(str(layer.get("nm", "")).strip())
            for layer in layers
        )
    )
    active_logger.info(
        "TGS pre-build final_layers_count=%s glyph_bank_exists_before_build=%s",
        layers_count,
        glyph_bank_exists_before_build,
    )
    marker_token = str(data.get(_X_MARKER_TOKEN_KEY) or "")

    def _remove_marker_token_recursive(node: Any) -> Any:
        if isinstance(node, dict):
            cleaned: dict[str, Any] = {}
            for key, value in node.items():
                if key == _X_MARKER_TOKEN_KEY:
                    continue
                cleaned[key] = _remove_marker_token_recursive(value)
            return cleaned
        if isinstance(node, list):
            return [_remove_marker_token_recursive(item) for item in node]
        return node

    json_payload = _remove_marker_token_recursive(data)
    compact_json, compressed = _encode_tgs_payload(json_payload)
    selected_strategy = "original"
    if len(compressed) > TELEGRAM_TGS_MAX_BYTES:
        best_payload = json_payload
        best_json = compact_json
        best_compressed = compressed
        best_strategy = selected_strategy
        optimization_passes: tuple[tuple[str, int, bool], ...] = (
            ("quantize_p4", 4, False),
            ("quantize_p3", 3, False),
            ("quantize_p3_strip_meta", 3, True),
            ("quantize_p2_strip_meta", 2, True),
            ("quantize_p1_strip_meta", 1, True),
        )
        for strategy_name, precision, strip_metadata in optimization_passes:
            candidate_payload = _shrink_lottie_payload(
                json_payload,
                float_precision=precision,
                strip_metadata=strip_metadata,
                at_root=True,
            )
            candidate_json, candidate_compressed = _encode_tgs_payload(candidate_payload)
            active_logger.info(
                "TGS size optimize attempt strategy=%s float_precision=%s strip_metadata=%s json_bytes=%s tgs_bytes=%s",
                strategy_name,
                precision,
                strip_metadata,
                len(candidate_json),
                len(candidate_compressed),
            )
            if len(candidate_compressed) < len(best_compressed):
                best_payload = candidate_payload
                best_json = candidate_json
                best_compressed = candidate_compressed
                best_strategy = strategy_name
            if len(candidate_compressed) <= TELEGRAM_TGS_MAX_BYTES:
                break

        if best_strategy != selected_strategy:
            json_payload = best_payload
            compact_json = best_json
            compressed = best_compressed
            selected_strategy = best_strategy
            active_logger.info(
                "TGS size optimize selected strategy=%s final_json_bytes=%s final_tgs_bytes=%s limit=%s",
                selected_strategy,
                len(compact_json),
                len(compressed),
                TELEGRAM_TGS_MAX_BYTES,
            )

    debug_root = os.getenv("EMOJI_TGS_DEBUG_DIR", "").strip()
    if debug_root:
        debug_dir = Path(debug_root).expanduser()
    else:
        debug_dir = Path(__file__).resolve().parents[2] / "temp" / "tgs_debug"
    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        suffix = uuid.uuid4().hex[:10]
        json_path = debug_dir / f"final_{suffix}.json"
        tgs_path = debug_dir / f"final_{suffix}.tgs"
        json_path.write_bytes(compact_json)
        tgs_path.write_bytes(compressed)
        active_logger.info(
            "TGS debug dump saved json=%s tgs=%s",
            str(json_path),
            str(tgs_path),
        )
        with _X_RENDER_MARKER_LOCK:
            marker = _X_RENDER_MARKER_BY_TOKEN.get(marker_token)
            marker = copy.deepcopy(marker) if isinstance(marker, dict) else None
        if marker:
            marker["debug_dump_id"] = suffix
            with _X_RENDER_MARKER_LOCK:
                _X_RENDER_MARKER_BY_TOKEN[marker_token] = copy.deepcopy(marker)
                _LAST_X_RENDER_MARKER = copy.deepcopy(marker)
            active_logger.info(
                (
                    "X placement build marker debug_dump_id=%s marker_id=%s x_mode=%s x_profile=%s x_formula=%s "
                    "chosen_target_x=%s source_ks_p_x=%s final_tr_p_x=%s single_x_strategy_locked=%s layer=%s marker_token=%s"
                ),
                suffix,
                marker.get("marker_id"),
                marker.get("x_mode"),
                marker.get("x_profile"),
                marker.get("x_formula"),
                marker.get("chosen_target_x"),
                marker.get("source_ks_p_x"),
                marker.get("final_tr_p_x"),
                marker.get("single_x_strategy_locked"),
                marker.get("layer"),
                marker_token or None,
            )
        else:
            active_logger.info(
                "X placement build marker debug_dump_id=%s marker_id=None reason=no_marker_for_payload marker_token=%s",
                suffix,
                marker_token or None,
            )
    except Exception:
        active_logger.error("Failed to save TGS debug dump", exc_info=True)

    active_logger.info(
        "TGS built json_bytes=%s tgs_bytes=%s compression_ratio=%.3f size_strategy=%s",
        len(compact_json),
        len(compressed),
        (len(compressed) / max(1, len(compact_json))),
        selected_strategy,
    )
    if len(compressed) > TELEGRAM_TGS_MAX_BYTES:
        active_logger.warning(
            "TGS size exceeds Telegram animated sticker limit tgs_bytes=%s limit=%s",
            len(compressed),
            TELEGRAM_TGS_MAX_BYTES,
        )
    return compressed


def process_template_file(
    template_path: str | Path,
    new_text: str,
    stroke_hex: str,
    elements_hex: str,
    enable_recolor: bool = True,
    text_fill_hex: str | None = None,
    text_stroke_hex: str | None = None,
    apply_text_color_even_when_recolor_disabled: bool = True,
    force_text_position: bool = True,
    text_position_override: list[float] | None = None,
    text_box_config: TextBoxConfig | None = None,
    force_min_text_size: float | None = None,
    min_visible_text_size_warning: float = 20.0,
    text_debug_mode: bool = True,
    debug_move_text_layer_to_top: bool = False,
    debug_text_layer_name: str = TARGET_TEXT_LAYER_NAME,
) -> bytes:
    _ensure_file_and_console_logging()
    logger = logging.getLogger(__name__)
    path = Path(template_path).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    logger.info(
        (
            "Generation start template=%s text=%r stroke=%s elements=%s enable_recolor=%s "
            "text_fill=%s text_stroke=%s apply_text_color_even_when_recolor_disabled=%s "
            "force_text_position=%s text_position_override=%s text_box_config=%s "
            "force_min_text_size=%s min_visible_text_size_warning=%s text_debug_mode=%s "
            "debug_move_text_layer_to_top=%s debug_text_layer_name=%s"
        ),
        str(path),
        new_text,
        stroke_hex,
        elements_hex,
        enable_recolor,
        text_fill_hex,
        text_stroke_hex,
        apply_text_color_even_when_recolor_disabled,
        force_text_position,
        _serialize_for_log(text_position_override),
        _serialize_for_log(text_box_config),
        force_min_text_size,
        min_visible_text_size_warning,
        text_debug_mode,
        debug_move_text_layer_to_top,
        debug_text_layer_name,
    )
    data = read_json_file(path)
    replace_text_in_lottie(
        data,
        new_text,
        force_text_position=force_text_position,
        text_position_override=text_position_override,
        text_box_config=text_box_config,
        force_min_text_size=force_min_text_size,
        min_visible_text_size_warning=min_visible_text_size_warning,
        text_debug_mode=text_debug_mode,
        template_name=path.name,
        logger=logger,
    )
    if enable_recolor:
        recolor_lottie(data, stroke_hex=stroke_hex, elements_hex=elements_hex, logger=logger)
    else:
        logger.info("Recolor skipped template=%s reason=enable_recolor_false", str(path))
        if apply_text_color_even_when_recolor_disabled:
            effective_fill = text_fill_hex or elements_hex or "#FFFFFF"
            effective_stroke = text_stroke_hex if text_stroke_hex is not None else (stroke_hex or "#111111")
            update_text_layer_colors(
                data,
                text_fill_hex=effective_fill,
                text_stroke_hex=effective_stroke,
                logger=logger,
            )
    if debug_move_text_layer_to_top:
        move_text_layer_to_top(
            data=data,
            layer_name=debug_text_layer_name,
            logger=logger,
        )
    before_shape_injection = copy.deepcopy(data)
    inject_text_shapes(
        data=data,
        layer_name=TARGET_TEXT_LAYER_NAME,
        template_name=path.name,
        logger=logger,
    )
    _log_shape_pipeline_diff(
        before_data=before_shape_injection,
        after_data=data,
        logger=logger,
    )
    remove_glyph_bank_layers(data=data, logger=logger)
    return build_tgs_bytes(data, logger=logger)


class LottieService:
    def __init__(self) -> None:
        _ensure_file_and_console_logging()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("LottieService initialized")

    def load_lottie_json(self, template_path: str | Path) -> dict[str, Any]:
        path = Path(template_path).expanduser()
        if not path.is_absolute():
            path = path.resolve()
        self._logger.info("Loading template path=%s", str(path))
        try:
            data = read_json_file(path)
            self._logger.info("Template loaded path=%s", str(path))
            return data
        except Exception:
            self._logger.error("Failed to load template path=%s", str(path), exc_info=True)
            raise

    def replace_text(
        self,
        data: dict[str, Any],
        new_text: str,
        target_layer_names: set[str] | None = None,
        force_text_position: bool = True,
        text_position_override: list[float] | None = None,
        text_box_config: TextBoxConfig | None = None,
        force_min_text_size: float | None = None,
        min_visible_text_size_warning: float = 20.0,
        text_debug_mode: bool = True,
        template_name: str | None = None,
    ) -> LottieProcessingStats:
        self._logger.info(
            (
                "Text replacement start text=%r force_text_position=%s text_position_override=%s text_box_config=%s "
                "force_min_text_size=%s min_visible_text_size_warning=%s text_debug_mode=%s"
            ),
            new_text,
            force_text_position,
            _serialize_for_log(text_position_override),
            _serialize_for_log(text_box_config),
            force_min_text_size,
            min_visible_text_size_warning,
            text_debug_mode,
        )
        try:
            return replace_text_in_lottie(
                data=data,
                new_text=new_text,
                target_layer_names=target_layer_names,
                force_text_position=force_text_position,
                text_position_override=text_position_override,
                text_box_config=text_box_config,
                force_min_text_size=force_min_text_size,
                min_visible_text_size_warning=min_visible_text_size_warning,
                text_debug_mode=text_debug_mode,
                template_name=template_name,
                logger=self._logger,
            )
        except Exception:
            self._logger.error("Text replacement failed", exc_info=True)
            raise

    def move_text_layer_to_top(
        self,
        data: dict[str, Any],
        layer_name: str = TARGET_TEXT_LAYER_NAME,
    ) -> bool:
        self._logger.info(
            "Debug move text layer to top request layer_name=%s",
            layer_name,
        )
        try:
            return move_text_layer_to_top(
                data=data,
                layer_name=layer_name,
                logger=self._logger,
            )
        except Exception:
            self._logger.error(
                "Debug move text layer to top failed layer_name=%s",
                layer_name,
                exc_info=True,
            )
            raise

    def recolor(
        self,
        data: dict[str, Any],
        stroke_hex: str,
        elements_hex: str,
        bg_markers: tuple[str, ...] | None = None,
    ) -> LottieProcessingStats:
        self._logger.info(
            "Recolor start stroke=%s elements=%s bg_markers=%s",
            stroke_hex,
            elements_hex,
            bg_markers or DEFAULT_BG_MARKERS,
        )
        try:
            return recolor_lottie(
                data=data,
                stroke_hex=stroke_hex,
                elements_hex=elements_hex,
                bg_markers=bg_markers,
                logger=self._logger,
            )
        except Exception:
            self._logger.error("Recolor failed", exc_info=True)
            raise

    def recolor_text_layers(
        self,
        data: dict[str, Any],
        text_fill_hex: str,
        text_stroke_hex: str | None = None,
    ) -> LottieProcessingStats:
        self._logger.info(
            "Text color update start fill=%s stroke=%s",
            text_fill_hex,
            text_stroke_hex,
        )
        try:
            return update_text_layer_colors(
                data=data,
                text_fill_hex=text_fill_hex,
                text_stroke_hex=text_stroke_hex,
                logger=self._logger,
            )
        except Exception:
            self._logger.error("Text color update failed", exc_info=True)
            raise

    def build_tgs(self, data: dict[str, Any]) -> bytes:
        self._logger.info("TGS build start")
        try:
            return build_tgs_bytes(data, logger=self._logger)
        except Exception:
            self._logger.error("TGS build failed", exc_info=True)
            raise

    def process_template_data(
        self,
        source_data: dict[str, Any],
        new_text: str,
        stroke_hex: str,
        elements_hex: str,
        enable_recolor: bool = True,
        text_fill_hex: str | None = None,
        text_stroke_hex: str | None = None,
        apply_text_color_even_when_recolor_disabled: bool = True,
        force_text_position: bool = True,
        text_position_override: list[float] | None = None,
        text_box_config: TextBoxConfig | None = None,
        force_min_text_size: float | None = None,
        min_visible_text_size_warning: float = 20.0,
        text_debug_mode: bool = True,
        debug_move_text_layer_to_top: bool = False,
        debug_text_layer_name: str = TARGET_TEXT_LAYER_NAME,
        template_name: str | None = None,
    ) -> tuple[dict[str, Any], LottieProcessingStats]:
        self._logger.info(
            (
                "Generation start (in-memory template) text=%r stroke=%s elements=%s enable_recolor=%s "
                "text_fill=%s text_stroke=%s apply_text_color_even_when_recolor_disabled=%s "
                "force_text_position=%s text_position_override=%s text_box_config=%s "
                "force_min_text_size=%s min_visible_text_size_warning=%s text_debug_mode=%s "
                "debug_move_text_layer_to_top=%s debug_text_layer_name=%s template_name=%s"
            ),
            new_text,
            stroke_hex,
            elements_hex,
            enable_recolor,
            text_fill_hex,
            text_stroke_hex,
            apply_text_color_even_when_recolor_disabled,
            force_text_position,
            _serialize_for_log(text_position_override),
            _serialize_for_log(text_box_config),
            force_min_text_size,
            min_visible_text_size_warning,
            text_debug_mode,
            debug_move_text_layer_to_top,
            debug_text_layer_name,
            template_name,
        )
        try:
            payload = copy.deepcopy(source_data)
            text_stats = self.replace_text(
                payload,
                new_text,
                force_text_position=force_text_position,
                text_position_override=text_position_override,
                text_box_config=text_box_config,
                force_min_text_size=force_min_text_size,
                min_visible_text_size_warning=min_visible_text_size_warning,
                text_debug_mode=text_debug_mode,
                template_name=template_name,
            )
            text_color_stats = LottieProcessingStats()
            if enable_recolor:
                recolor_stats = self.recolor(
                    payload,
                    stroke_hex=stroke_hex,
                    elements_hex=elements_hex,
                )
            else:
                recolor_stats = LottieProcessingStats()
                self._logger.info("Recolor skipped reason=enable_recolor_false")
                if apply_text_color_even_when_recolor_disabled:
                    effective_fill = text_fill_hex or elements_hex or "#FFFFFF"
                    effective_stroke = text_stroke_hex if text_stroke_hex is not None else (stroke_hex or "#111111")
                    text_color_stats = self.recolor_text_layers(
                        payload,
                        text_fill_hex=effective_fill,
                        text_stroke_hex=effective_stroke,
                    )
            if debug_move_text_layer_to_top:
                move_text_layer_to_top(
                    data=payload,
                    layer_name=debug_text_layer_name,
                    logger=self._logger,
                )
            before_shape_injection = copy.deepcopy(payload)
            inject_text_shapes(
                data=payload,
                layer_name=TARGET_TEXT_LAYER_NAME,
                template_name=template_name,
                logger=self._logger,
            )
            template_name_norm = (template_name or "").strip().lower()
            if template_name_norm in {
                _EMOJI8_NESTED_TEXT_TEMPLATE_FILE,
                _EMOJI10_TEMPLATE_FILE,
                _EMOJI14_TEMPLATE_FILE,
                _EMOJI18_TEMPLATE_FILE,
                _EMOJI24_TEMPLATE_FILE,
            }:
                nested_text_layers_found = 0
                nested_text_layers_converted = 0
                assets = payload.get("assets")
                if isinstance(assets, list):
                    for asset in assets:
                        if not isinstance(asset, dict):
                            continue
                        asset_layers = asset.get("layers")
                        if not isinstance(asset_layers, list):
                            continue
                        if template_name_norm == _EMOJI14_TEMPLATE_FILE:
                            if _as_float(asset.get("w")) is None:
                                root_w = _as_float(payload.get("w"))
                                if root_w is not None:
                                    asset["w"] = int(round(root_w))
                            if _as_float(asset.get("h")) is None:
                                root_h = _as_float(payload.get("h"))
                                if root_h is not None:
                                    asset["h"] = int(round(root_h))
                        if template_name_norm == _EMOJI14_TEMPLATE_FILE:
                            target_layers_in_asset = [
                                layer
                                for layer in asset_layers
                                if isinstance(layer, dict)
                                and layer.get("ty") == 5
                                and not _is_glyph_bank_layer(str(layer.get("nm", "")).strip())
                            ]
                        else:
                            target_layers_in_asset = [
                                layer
                                for layer in asset_layers
                                if isinstance(layer, dict)
                                and layer.get("ty") == 5
                                and not _is_glyph_bank_layer(str(layer.get("nm", "")).strip())
                                and _normalize_name(str(layer.get("nm", "")).strip()) == _normalize_name(TARGET_TEXT_LAYER_NAME)
                            ]
                        if target_layers_in_asset:
                            nested_text_layers_found += len(target_layers_in_asset)
                            nested_text_layers_converted += inject_text_shapes(
                                data=asset,
                                layer_name=TARGET_TEXT_LAYER_NAME,
                                template_name=template_name,
                                logger=self._logger,
                            )
                        remove_glyph_bank_layers(data=asset, logger=self._logger)
                remaining_text_layers_anywhere = _count_non_glyph_text_layers_anywhere(payload)
                self._logger.info(
                    "Nested text conversion template_name=%s nested_text_layers_found=%s nested_text_layers_converted=%s remaining_text_layers_anywhere_in_payload=%s",
                    template_name or None,
                    nested_text_layers_found,
                    nested_text_layers_converted,
                    remaining_text_layers_anywhere,
                )
            _log_shape_pipeline_diff(
                before_data=before_shape_injection,
                after_data=payload,
                logger=self._logger,
            )
            remove_glyph_bank_layers(data=payload, logger=self._logger)
            merged = LottieProcessingStats(
                text_layers_found=text_stats.text_layers_found,
                text_keyframes_found=text_stats.text_keyframes_found,
                text_keyframes_updated=text_stats.text_keyframes_updated,
                text_fill_colors_found=recolor_stats.text_fill_colors_found + text_color_stats.text_fill_colors_found,
                text_fill_colors_updated=recolor_stats.text_fill_colors_updated + text_color_stats.text_fill_colors_updated,
                text_stroke_colors_found=recolor_stats.text_stroke_colors_found + text_color_stats.text_stroke_colors_found,
                text_stroke_colors_updated=recolor_stats.text_stroke_colors_updated + text_color_stats.text_stroke_colors_updated,
                fill_nodes_found=recolor_stats.fill_nodes_found,
                stroke_nodes_found=recolor_stats.stroke_nodes_found,
                fill_nodes_recolored=recolor_stats.fill_nodes_recolored,
                stroke_nodes_recolored=recolor_stats.stroke_nodes_recolored,
                color_arrays_updated=recolor_stats.color_arrays_updated + text_color_stats.color_arrays_updated,
                skipped_color_nodes=recolor_stats.skipped_color_nodes + text_color_stats.skipped_color_nodes,
                text_layout_keyframes_logged=text_stats.text_layout_keyframes_logged,
                text_size_forced=text_stats.text_size_forced,
                text_visibility_warnings=text_stats.text_visibility_warnings,
                skipped_nodes=list(recolor_stats.skipped_nodes) + list(text_color_stats.skipped_nodes),
            )
            return payload, merged
        except Exception:
            self._logger.error("Generation failed (in-memory template)", exc_info=True)
            raise

    def process_template_file(
        self,
        template_path: str | Path,
        new_text: str,
        stroke_hex: str,
        elements_hex: str,
        enable_recolor: bool = True,
        text_fill_hex: str | None = None,
        text_stroke_hex: str | None = None,
        apply_text_color_even_when_recolor_disabled: bool = True,
        force_text_position: bool = True,
        text_position_override: list[float] | None = None,
        text_box_config: TextBoxConfig | None = None,
        force_min_text_size: float | None = None,
        min_visible_text_size_warning: float = 20.0,
        text_debug_mode: bool = True,
        debug_move_text_layer_to_top: bool = False,
        debug_text_layer_name: str = TARGET_TEXT_LAYER_NAME,
    ) -> tuple[bytes, LottieProcessingStats]:
        path = Path(template_path).expanduser()
        if not path.is_absolute():
            path = path.resolve()
        self._logger.info(
            (
                "Generation start template=%s text=%r stroke=%s elements=%s enable_recolor=%s "
                "text_fill=%s text_stroke=%s apply_text_color_even_when_recolor_disabled=%s "
                "force_text_position=%s text_position_override=%s text_box_config=%s "
                "force_min_text_size=%s min_visible_text_size_warning=%s text_debug_mode=%s "
                "debug_move_text_layer_to_top=%s debug_text_layer_name=%s"
            ),
            str(path),
            new_text,
            stroke_hex,
            elements_hex,
            enable_recolor,
            text_fill_hex,
            text_stroke_hex,
            apply_text_color_even_when_recolor_disabled,
            force_text_position,
            _serialize_for_log(text_position_override),
            _serialize_for_log(text_box_config),
            force_min_text_size,
            min_visible_text_size_warning,
            text_debug_mode,
            debug_move_text_layer_to_top,
            debug_text_layer_name,
        )
        try:
            data = self.load_lottie_json(path)
            processed, stats = self.process_template_data(
                source_data=data,
                new_text=new_text,
                stroke_hex=stroke_hex,
                elements_hex=elements_hex,
                enable_recolor=enable_recolor,
                text_fill_hex=text_fill_hex,
                text_stroke_hex=text_stroke_hex,
                apply_text_color_even_when_recolor_disabled=apply_text_color_even_when_recolor_disabled,
                force_text_position=force_text_position,
                text_position_override=text_position_override,
                text_box_config=text_box_config,
                force_min_text_size=force_min_text_size,
                min_visible_text_size_warning=min_visible_text_size_warning,
                text_debug_mode=text_debug_mode,
                debug_move_text_layer_to_top=debug_move_text_layer_to_top,
                debug_text_layer_name=debug_text_layer_name,
                template_name=path.name,
            )
            tgs = self.build_tgs(processed)
            self._logger.info(
                (
                    "Generation done template=%s text_layers=%s text_keyframes=%s "
                    "text_layout_logged=%s text_size_forced=%s text_visibility_warnings=%s "
                    "fill=%s/%s stroke=%s/%s skipped=%s"
                ),
                str(path),
                stats.text_layers_found,
                stats.text_keyframes_updated,
                stats.text_layout_keyframes_logged,
                stats.text_size_forced,
                stats.text_visibility_warnings,
                stats.fill_nodes_recolored,
                stats.fill_nodes_found,
                stats.stroke_nodes_recolored,
                stats.stroke_nodes_found,
                stats.skipped_color_nodes,
            )
            return tgs, stats
        except Exception:
            self._logger.error("Generation failed template=%s", str(path), exc_info=True)
            raise

