from __future__ import annotations

import logging
import uuid
from pathlib import Path

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from PIL import Image

from app.config import Settings
from app.keyboards.preview import preview_kb
from app.models.preview_result import PreviewAsset
from app.services.lottie_service import get_last_x_render_marker
from app.services.preview_service import PreviewService
from app.services.template_repository import TemplateRepository
from app.states import CreatePackState
from app.ui import build_preview_summary_text

logger = logging.getLogger(__name__)


def build_blue_preview_collage(
    *,
    preview_assets: list[PreviewAsset],
    user_id: int,
) -> str | None:
    source_paths = [Path(asset.output_path) for asset in preview_assets if Path(asset.output_path).exists()]
    if not source_paths:
        return None

    count = len(source_paths)
    columns = min(5, max(1, count))
    rows = (count + columns - 1) // columns
    tile_w = 180
    tile_h = 180
    gap = 18
    margin = 28

    canvas_w = margin * 2 + columns * tile_w + (columns - 1) * gap
    canvas_h = margin * 2 + rows * tile_h + (rows - 1) * gap
    canvas = Image.new("RGB", (canvas_w, canvas_h), (24, 91, 214))
    resampling = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

    for idx, path in enumerate(source_paths):
        row = idx // columns
        col = idx % columns
        tile_x = margin + col * (tile_w + gap)
        tile_y = margin + row * (tile_h + gap)
        try:
            with Image.open(path) as image:
                image_rgba = image.convert("RGBA")
                image_rgba.thumbnail((tile_w, tile_h), resampling)
                paste_x = tile_x + (tile_w - image_rgba.width) // 2
                paste_y = tile_y + (tile_h - image_rgba.height) // 2
                canvas.paste(image_rgba, (paste_x, paste_y), image_rgba)
        except Exception:
            logger.warning("Preview collage skipped source path=%s", path)
            continue

    output_path = source_paths[0].parent / f"preview_sheet_{user_id}_{uuid.uuid4().hex[:8]}.png"
    canvas.save(output_path, format="PNG", optimize=True)
    return str(output_path.resolve())


async def build_and_send_preview(
    target: Message | CallbackQuery,
    state: FSMContext,
    template_repository: TemplateRepository,
    preview_service: PreviewService,
    settings: Settings,
) -> None:
    if isinstance(target, CallbackQuery):
        if target.message is None:
            return
        chat_message = target.message
        user_id = target.from_user.id
    else:
        if target.from_user is None:
            return
        chat_message = target
        user_id = target.from_user.id

    data = await state.get_data()
    category_id = data.get("selected_category_id")
    input_text = data.get("input_text")
    selected_template_ids = data.get("selected_template_ids", [])

    if not isinstance(category_id, str):
        await chat_message.answer("Категория не выбрана.")
        return
    if not isinstance(input_text, str) or not input_text.strip():
        await chat_message.answer("Сначала отправьте текст.")
        return
    if not selected_template_ids:
        await chat_message.answer("Сначала выберите шаблоны.")
        return

    category = template_repository.get_category(category_id)
    if category is None:
        await chat_message.answer("Категория не найдена.")
        return

    templates = template_repository.get_templates_by_ids(list(selected_template_ids))
    if not templates:
        await chat_message.answer("Не удалось найти выбранные шаблоны.")
        return

    pack_title = str(data.get("pack_title", "")).strip()
    if not pack_title:
        pack_title = input_text

    logger.info(
        "Preview start user_id=%s category=%s text=%s templates=%s",
        user_id,
        category_id,
        input_text,
        [item.id for item in templates],
    )

    try:
        context = await preview_service.build_preview_context(
            user_id=user_id,
            category_id=category_id,
            templates=templates,
            input_text=input_text,
            stroke_color=settings.default_stroke_color,
            elements_color=settings.default_elements_color,
        )
    except Exception as exc:
        logger.exception("Preview failed user_id=%s error=%s", user_id, exc)
        await chat_message.answer(
            "Не удалось собрать предпросмотр. Проверьте выбранные шаблоны и попробуйте снова."
        )
        return

    await state.update_data(
        preview_context_id=context.context_id,
        selected_template_ids=context.selected_template_ids,
    )
    await state.set_state(CreatePackState.preview)

    if context.preview_assets:
        marker = get_last_x_render_marker()
        marker_caption = ""
        if marker:
            marker_caption = (
                f"\nbuild={marker.get('debug_dump_id') or '-'}"
                f" x_mode={marker.get('x_mode') or '-'}"
                f" chosen_x={marker.get('chosen_target_x')}"
                f" source_x={marker.get('source_ks_p_x')}"
                f" final_x={marker.get('final_tr_p_x')}"
                f" locked={marker.get('single_x_strategy_locked')}"
            )
            logger.info(
                "Preview marker attached build=%s marker_id=%s x_mode=%s chosen_x=%s source_x=%s final_x=%s locked=%s",
                marker.get("debug_dump_id"),
                marker.get("marker_id"),
                marker.get("x_mode"),
                marker.get("chosen_target_x"),
                marker.get("source_ks_p_x"),
                marker.get("final_tr_p_x"),
                marker.get("single_x_strategy_locked"),
            )

        collage_path = build_blue_preview_collage(
            preview_assets=context.preview_assets,
            user_id=user_id,
        )
        caption = f"Превью: {len(context.preview_assets)}{marker_caption}"
        if collage_path:
            await chat_message.answer_photo(photo=FSInputFile(collage_path), caption=caption)
            Path(collage_path).unlink(missing_ok=True)
        else:
            await chat_message.answer_photo(photo=FSInputFile(context.preview_assets[0].output_path), caption=caption)
    else:
        await chat_message.answer("PNG предпросмотр не собрался, показываю текстовую сводку.")

    summary_text = build_preview_summary_text(
        category=category,
        text=input_text,
        templates=templates,
        price=context.price,
        pack_title=f"{pack_title} @Hep_kerstickbot",
    )
    await chat_message.answer(summary_text, reply_markup=preview_kb())
    if isinstance(target, CallbackQuery):
        await target.answer()
