from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.models.payment import PaymentInvoice, PaymentStatus


class PaymentService(ABC):
    @abstractmethod
    async def create_invoice(self, user_id: int, amount: float, description: str) -> PaymentInvoice:
        raise NotImplementedError

    @abstractmethod
    async def check_payment(self, invoice_id: str, user_id: int) -> PaymentStatus:
        raise NotImplementedError

    @abstractmethod
    async def mark_paid(self, invoice_id: str) -> None:
        raise NotImplementedError


class FakePaymentService(PaymentService):
    def __init__(self) -> None:
        self._invoices: dict[str, PaymentInvoice] = {}
        self._lock = asyncio.Lock()

    async def create_invoice(self, user_id: int, amount: float, description: str) -> PaymentInvoice:
        invoice_id = uuid.uuid4().hex[:12]
        invoice = PaymentInvoice(
            id=invoice_id,
            user_id=user_id,
            amount=amount,
            description=description,
            status=PaymentStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )
        async with self._lock:
            self._invoices[invoice_id] = invoice
        return invoice

    async def check_payment(self, invoice_id: str, user_id: int) -> PaymentStatus:
        async with self._lock:
            invoice = self._invoices.get(invoice_id)
        if invoice is None:
            return PaymentStatus.FAILED
        if invoice.user_id != user_id:
            return PaymentStatus.FAILED
        return invoice.status

    async def mark_paid(self, invoice_id: str) -> None:
        async with self._lock:
            invoice = self._invoices.get(invoice_id)
            if invoice:
                invoice.status = PaymentStatus.PAID

