from __future__ import annotations

from dataclasses import dataclass, field

from app.models.pack_result import PackCreationResult


@dataclass(slots=True)
class UserProfile:
    user_id: int
    balance: float = 20.0
    packs: list[PackCreationResult] = field(default_factory=list)

