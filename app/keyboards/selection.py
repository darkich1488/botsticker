from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import PickModeCallback, TemplateActionCallback, TemplatePageCallback, TemplateToggleCallback
from app.models.template import TemplateModel

_BASIC_TEMPLATE_ICONS: dict[int, str] = {
    1: "📱",
    2: "🎯",
    3: "🌼",
    4: "🤝",
    5: "⛓️",
    6: "⌚",
    7: "🤠",
    8: "🧎",
    9: "🎭",
    10: "🎰",
}


def _template_button_text(template: TemplateModel, selected: bool) -> str:
    icon = "🧩"
    if template.category_id == "basic":
        icon = _BASIC_TEMPLATE_ICONS.get(template.order_index, icon)
    selected_mark = "✅" if selected else ""
    return f"{icon} {template.order_index}{selected_mark}"


def pick_mode_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="🎯 Выбрать самому",
        callback_data=PickModeCallback(mode="manual").pack(),
    )
    kb.button(
        text="🎲 Случайный пак",
        callback_data=PickModeCallback(mode="random").pack(),
    )
    kb.button(
        text="↩️ Назад",
        callback_data=PickModeCallback(mode="back").pack(),
    )
    kb.adjust(1)
    return kb.as_markup()


def template_selection_kb(
    templates: Sequence[TemplateModel],
    selected_template_ids: set[int],
    current_page: int,
    total_pages: int,
    supports_recolor: bool,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for template in templates:
        kb.button(
            text=_template_button_text(template, template.id in selected_template_ids),
            callback_data=TemplateToggleCallback(template_id=template.id).pack(),
        )
    kb.adjust(4)

    kb.button(
        text="⬅️",
        callback_data=TemplatePageCallback(page=max(1, current_page - 1)).pack(),
    )
    kb.button(
        text=f"{current_page}/{total_pages}",
        callback_data=TemplateActionCallback(action="noop").pack(),
    )
    kb.button(
        text="➡️",
        callback_data=TemplatePageCallback(page=min(total_pages, current_page + 1)).pack(),
    )

    kb.button(
        text="🔢 Выбрать номер страницы",
        callback_data=TemplateActionCallback(action="page_pick").pack(),
    )
    kb.button(
        text="🎲 Случайный выбор",
        callback_data=TemplateActionCallback(action="random_here").pack(),
    )
    kb.button(
        text="✅ Выбрать все",
        callback_data=TemplateActionCallback(action="select_all").pack(),
    )
    kb.button(
        text="💳 Перейти к оплате",
        callback_data=TemplateActionCallback(action="to_payment").pack(),
    )
    kb.button(
        text="↩️ Назад",
        callback_data=TemplateActionCallback(action="back_mode").pack(),
    )
    kb.adjust(4, 3, 1, 1, 1, 1, 1)
    return kb.as_markup()
