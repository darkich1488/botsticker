from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemplateModel:
    id: int
    category_id: str
    file_name: str
    file_path: str
    preview_path: str | None
    supports_text: bool
    supports_recolor: bool
    order_index: int

