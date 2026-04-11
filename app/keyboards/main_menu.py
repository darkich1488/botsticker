from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import MainMenuCallback


def main_menu_kb(include_admin: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="🧩 Новый набор",
        callback_data=MainMenuCallback(action="new_pack").pack(),
    )
    if include_admin:
        kb.button(
            text="📣 Рассылка",
            callback_data=MainMenuCallback(action="admin_broadcast").pack(),
        )
    kb.adjust(1)
    return kb.as_markup()
