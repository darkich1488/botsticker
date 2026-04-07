from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
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
    11: "😈",
    12: "📚",
    13: "💀",
    14: "🐸",
    15: "⌚",
    16: "✈️",
    17: "🧴",
    18: "🎳",
    19: "🔫",
    20: "⚽",
    21: "🪧",
    22: "💻",
    23: "❤️",
    24: "🦆",
}

_BASIC_TEMPLATE_CUSTOM_EMOJI_IDS: dict[int, str] = {
    1: "5382134255759433576",
    2: "5382035918188222993",
    3: "5379917588778228005",
    4: "5382035016245090266",
    5: "5382237511068197195",
    6: "5379934008438201698",
    7: "5379966959427298462",
    8: "5379580360831050772",
    9: "5379984740591899595",
    10: "5379918593800578432",
    11: "5380103200084892532",
    12: "5380055470113333568",
    13: "5379908835634883978",
    14: "5380036121285668045",
    15: "5382079881473464135",
    16: "5381965321810780880",
    17: "5379583491862209123",
    18: "5381992813896441341",
    19: "5379594980899723701",
    20: "5380000649150768346",
    21: "5379943465956187500",
    22: "5379592910725492211",
    23: "5379741928910790930",
    24: "5382168916145513392",
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
    has_selected = len(selected_template_ids) > 0

    template_buttons: list[InlineKeyboardButton] = []
    for template in templates:
        is_selected = template.id in selected_template_ids
        button_text = _template_button_text(template, is_selected)
        button_payload: dict[str, str] = {
            "text": button_text,
            "callback_data": TemplateToggleCallback(template_id=template.id).pack(),
        }
        if template.category_id == "basic":
            custom_emoji_id = _BASIC_TEMPLATE_CUSTOM_EMOJI_IDS.get(template.order_index)
            if custom_emoji_id:
                button_payload["icon_custom_emoji_id"] = custom_emoji_id
        template_buttons.append(InlineKeyboardButton(**button_payload))

    for idx in range(0, len(template_buttons), 4):
        kb.row(*template_buttons[idx : idx + 4])

    if total_pages > 1:
        kb.row(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=TemplatePageCallback(page=max(1, current_page - 1)).pack(),
            ),
            InlineKeyboardButton(
                text=f"{current_page}/{total_pages}",
                callback_data=TemplateActionCallback(action="noop").pack(),
            ),
            InlineKeyboardButton(
                text="➡️",
                callback_data=TemplatePageCallback(page=min(total_pages, current_page + 1)).pack(),
            ),
        )
        kb.row(
            InlineKeyboardButton(
                text="🔢 Выбрать номер страницы",
                callback_data=TemplateActionCallback(action="page_pick").pack(),
            )
        )

    kb.row(
        InlineKeyboardButton(
            text="🎲 Случайный выбор",
            callback_data=TemplateActionCallback(action="random_here").pack(),
        )
    )
    kb.row(
        InlineKeyboardButton(
            text="✅ Выбрать все",
            callback_data=TemplateActionCallback(action="select_all").pack(),
        )
    )
    if has_selected:
        kb.row(
            InlineKeyboardButton(
                text="🧹 Скинуть выбор",
                callback_data=TemplateActionCallback(action="clear_selected").pack(),
            )
        )
        kb.row(
            InlineKeyboardButton(
                text="💳 Перейти к оплате",
                callback_data=TemplateActionCallback(action="to_payment").pack(),
            )
        )
    kb.row(
        InlineKeyboardButton(
            text="↩️ Назад",
            callback_data=TemplateActionCallback(action="back_mode").pack(),
        )
    )
    return kb.as_markup()
