from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PackCreationResult:
    pack_id: str
    pack_title: str
    addemoji_link: str
    public_link: str
    items_count: int
    metadata: dict[str, str] = field(default_factory=dict)

