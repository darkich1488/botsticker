from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TemplateCategory:
    id: str
    title: str
    description: str
    path_to_templates: str
    supports_recolor: bool

