from __future__ import annotations

from collections.abc import Sequence

from app.models.category import TemplateCategory
from app.models.template import TemplateModel


def build_main_menu_text(balance: float | None = None, can_create: int | None = None) -> str:
    return (
        "Привет! Здесь можно создать стикерпак из шаблонов.\n\n"
        "Нажмите «Новый набор», чтобы начать."
    )


def build_template_selection_text(
    category: TemplateCategory,
    current_page: int,
    total_pages: int,
    selected_count: int,
    total_templates: int,
    current_price: float,
) -> str:
    lines = [
        f"Пакет: {category.title}",
        f"Страница: {current_page}/{total_pages}",
        f"Выбрано шаблонов: {selected_count} из {total_templates}",
        f"Текущая цена: {current_price:.0f} ⭐",
        "",
        "Нажимайте номера для переключения выбора.",
    ]
    return "\n".join(lines)


def build_preview_summary_text(
    category: TemplateCategory,
    text: str,
    templates: Sequence[TemplateModel],
    price: float,
    pack_title: str,
) -> str:
    preview_names = ", ".join(str(item.order_index) for item in templates[:12])
    if len(templates) > 12:
        preview_names += ", ..."
    return (
        "Предпросмотр перед оплатой\n\n"
        f"Текст: {text}\n"
        f"Название набора: {pack_title}\n"
        f"Пакет: {category.title}\n"
        f"Количество шаблонов: {len(templates)}\n"
        f"Шаблоны: {preview_names or '-'}\n"
        f"Цена: {price:.0f} ⭐"
    )
