from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import PaymentActionCallback, PreviewActionCallback


def preview_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="💳 Перейти к оплате",
        callback_data=PreviewActionCallback(action="to_payment").pack(),
    )
    kb.button(
        text="↩️ Назад",
        callback_data=PreviewActionCallback(action="back_to_templates").pack(),
    )
    kb.adjust(1)
    return kb.as_markup()


def payment_kb(invoice_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="✅ Проверить оплату",
        callback_data=PaymentActionCallback(action="check", invoice_id=invoice_id).pack(),
    )
    kb.button(
        text="↩️ Назад",
        callback_data=PaymentActionCallback(action="cancel", invoice_id=invoice_id).pack(),
    )
    kb.adjust(1)
    return kb.as_markup()


def result_kb(pack_link: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 Посмотреть набор", url=pack_link)
    return kb.as_markup()
