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
    25: "👻",
    26: "🗡️",
    27: "☑️",
    28: "🪧",
    29: "🚗",
    30: "🐍",
}

_BASIC_TEMPLATE_CUSTOM_EMOJI_IDS: dict[int, str] = {
    1: "5386407370261829841",
    2: "5386556800763993908",
    3: "5386747763599910433",
    4: "5384308900780610564",
    5: "5386326831035095258",
    6: "5386545169992551732",
    7: "5386649404553861469",
    8: "5386732069789407569",
    9: "5386438680573420322",
    10: "5386310389900287272",
    11: "5386616479334572668",
    12: "5386527844094484499",
    13: "5386766012915944496",
    14: "5386552132134542007",
    15: "5386330838239581404",
    16: "5386818239718269493",
    17: "5386591345185954877",
    18: "5386799685459548546",
    19: "5386765501814838164",
    20: "5386644121744086287",
    21: "5386543808487922119",
    22: "5386821894735438281",
    23: "5386792087662400757",
    24: "5386638516811763501",
    25: "5386812029195557536",
    26: "5386308156517291684",
    27: "5386772863388784902",
    28: "5386687672712469515",
    29: "5386377881016372967",
    30: "5386406584282816605",
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
