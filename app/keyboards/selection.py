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
    31: "⌚",
    32: "📺",
    33: "🦆",
    34: "❤️",
    35: "⚰️",
    36: "👩",
    37: "🐻",
    38: "😈",
    39: "⚙️",
    40: "🥷",
    41: "✝️",
    42: "👑",
}

_BASIC_TEMPLATE_CUSTOM_EMOJI_IDS: dict[int, str] = {
    1: "5393420712553784286",
    2: "5393072266152024431",
    3: "5391300536307848082",
    4: "5393556592434126691",
    5: "5393264620557343614",
    6: "5393598223552128016",
    7: "5393169680305266803",
    8: "5391130249444498820",
    9: "5391219997081114972",
    10: "5393526991519534359",
    11: "5391061349579136275",
    12: "5391008203653815660",
    13: "5393523748819214934",
    14: "5391241862759617529",
    15: "5393080843201714117",
    16: "5391074084157166912",
    17: "5391153674196131626",
    18: "5393554311806492415",
    19: "5390993781153633840",
    20: "5391039170368018829",
    21: "5393172764091782368",
    22: "5391208825871178369",
    23: "5391302739626071381",
    24: "5393180430608407944",
    25: "5393411916460758237",
    26: "5391069230844125370",
    27: "5391280487400512257",
    28: "5391233032306862156",
    29: "5393117522222423300",
    30: "5393150035124852734",
    31: "5391214447983368594",
    32: "5390988412444514761",
    33: "5393231600848774361",
    34: "5393090803230872157",
    35: "5393333559077412432",
    36: "5393376856642724045",
    37: "5391370522799936423",
    38: "5391112064552964344",
    39: "5391012614585225902",
    40: "5390967324155090544",
    41: "5390838131538828163",
    42: "5390895409222687820",
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
