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
    43: "💻",
    44: "🦭",
    45: "🤘",
    46: "🫡",
    47: "🖥️",
    48: "⭐",
}

_BASIC_TEMPLATE_CUSTOM_EMOJI_IDS: dict[int, str] = {
    1: "5400175188576866778",
    2: "5400377842313764465",
    3: "5398102789547139580",
    4: "5397910658480118180",
    5: "5397748987321161881",
    6: "5397861717327779983",
    7: "5397571961654124805",
    8: "5397818548611490508",
    9: "5397792521109676629",
    10: "5397804641507385030",
    11: "5398087752866636159",
    12: "5398094199612545822",
    13: "5397648459316631860",
    14: "5397981976412071659",
    15: "5398105349347644324",
    16: "5398032395033155540",
    17: "5400012430791185890",
    18: "5398024118631181298",
    19: "5400000344753214548",
    20: "5397659441548006914",
    21: "5397672347924733479",
    22: "5399891926893762215",
    23: "5399947881727692549",
    24: "5397977011429874065",
    25: "5397660480930095881",
    26: "5400109058965410842",
    27: "5398027163762992189",
    28: "5400019792365130740",
    29: "5400059104200790771",
    30: "5397851276262282881",
    31: "5398090639084657309",
    32: "5400122373364030886",
    33: "5397883299538449969",
    34: "5397667236913650081",
    35: "5399958692160377572",
    36: "5397969263308871854",
    37: "5400337117433859932",
    38: "5398124058225187381",
    39: "5397708009038193162",
    40: "5397998859928509044",
    41: "5398029921131995874",
    42: "5397703830035014486",
    43: "5397839692735486814",
    44: "5398032124450219000",
    45: "5397879446952778506",
    46: "5398102544734002573",
    47: "5397673662184725148",
    48: "5400378344824936245",
}

_PASSPORT_TEMPLATE_ICONS: dict[int, str] = {
    1: "🪪",
    2: "🪪",
    3: "🪪",
    4: "🪪",
    5: "🪪",
    6: "🪪",
    7: "🪪",
}

_PASSPORT_TEMPLATE_CUSTOM_EMOJI_IDS: dict[int, str] = {
    1: "5415767612078464316",
    2: "5415912867872414343",
    3: "5416082325807079272",
    4: "5418322808381938043",
    5: "5416062281194708639",
    6: "5415882343539843711",
    7: "5416062886785096262",
}


def _template_button_text(template: TemplateModel, selected: bool) -> str:
    icon = "🧩"
    if template.category_id == "basic":
        icon = _BASIC_TEMPLATE_ICONS.get(template.order_index, icon)
    elif template.category_id == "passport":
        icon = _PASSPORT_TEMPLATE_ICONS.get(template.order_index, icon)
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
        elif template.category_id == "passport":
            custom_emoji_id = _PASSPORT_TEMPLATE_CUSTOM_EMOJI_IDS.get(template.order_index)
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
