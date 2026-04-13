from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import CategoryCallback, MainMenuCallback
from app.models.category import TemplateCategory


def categories_kb(categories: Sequence[TemplateCategory]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for category in categories:
        if category.id == "basic":
            prefix = "🟢"
        elif category.id == "passport":
            prefix = "🛂"
        else:
            prefix = "🛠️"
        kb.button(
            text=f"{prefix} {category.title}",
            callback_data=CategoryCallback(category_id=category.id).pack(),
        )
    kb.button(
        text="↩️ Назад",
        callback_data=MainMenuCallback(action="back_main").pack(),
    )
    kb.adjust(1)
    return kb.as_markup()
