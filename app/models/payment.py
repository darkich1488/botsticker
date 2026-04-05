from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


@dataclass(slots=True)
class PaymentInvoice:
    id: str
    user_id: int
    amount: float
    description: str
    status: PaymentStatus
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
