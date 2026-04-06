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

_BASIC_TEMPLATE_CUSTOM_EMOJI_IDS: dict[int, str] = {
    1: "5377853161207798110",
    2: "5375301637101362035",
    3: "5377713561885777676",
    4: "5377491937278335228",
    5: "5377463208242092370",
    6: "5375122919217208828",
    7: "5375378748944193571",
    8: "5377679674593811653",
    9: "5377671389601895642",
    10: "5377407648545149088",
    11: "5377680043960997502",
    12: "5377460944794326403",
    13: "5377846710166918564",
    14: "5377651830320832768",
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
        kb.button(**button_payload)
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
