from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class PreviewRenderResult:
    success: bool
    output_path: str | None
    frame_count: int
    width: int
    height: int
    error_message: str | None = None


@dataclass(slots=True)
class ProcessedTemplateData:
    template_id: int
    template_name: str
    processed_lottie: dict[str, Any]
    tgs_bytes: bytes
    text_replacements: int
    recolored_nodes: int


@dataclass(slots=True)
class PreviewAsset:
    template_id: int
    media_type: str
    output_path: str
    render_result: PreviewRenderResult


@dataclass(slots=True)
class PreviewContext:
    context_id: str
    user_id: int
    category_id: str
    input_text: str
    stroke_color: str
    elements_color: str
    selected_template_ids: list[int]
    items: list[ProcessedTemplateData]
    preview_assets: list[PreviewAsset]
    price: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

