from __future__ import annotations

import logging

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.config import Settings
from app.ui import build_preview_summary_text
from app.keyboards.preview import preview_kb
from app.services.lottie_service import get_last_x_render_marker
from app.services.preview_service import PreviewService
from app.services.template_repository import TemplateRepository
from app.states import CreatePackState

logger = logging.getLogger(__name__)


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
        await chat_message.answer("РљР°С‚РµРіРѕСЂРёСЏ РЅРµ РІС‹Р±СЂР°РЅР°.")
        return
    if not isinstance(input_text, str) or not input_text.strip():
        await chat_message.answer("РЎРЅР°С‡Р°Р»Р° РѕС‚РїСЂР°РІСЊС‚Рµ С‚РµРєСЃС‚.")
        return
    if not selected_template_ids:
        await chat_message.answer("РЎРЅР°С‡Р°Р»Р° РІС‹Р±РµСЂРёС‚Рµ С€Р°Р±Р»РѕРЅС‹.")
        return

    category = template_repository.get_category(category_id)
    if category is None:
        await chat_message.answer("РљР°С‚РµРіРѕСЂРёСЏ РЅРµ РЅР°Р№РґРµРЅР°.")
        return

    templates = template_repository.get_templates_by_ids(list(selected_template_ids))
    if not templates:
        await chat_message.answer("РќРµ СѓРґР°Р»РѕСЃСЊ РЅР°Р№С‚Рё РІС‹Р±СЂР°РЅРЅС‹Рµ С€Р°Р±Р»РѕРЅС‹.")
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
            "РќРµ СѓРґР°Р»РѕСЃСЊ СЃРѕР±СЂР°С‚СЊ РїСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ. РџСЂРѕРІРµСЂСЊС‚Рµ РІС‹Р±СЂР°РЅРЅС‹Рµ С€Р°Р±Р»РѕРЅС‹ Рё РїРѕРїСЂРѕР±СѓР№С‚Рµ СЃРЅРѕРІР°."
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
        for index, asset in enumerate(context.preview_assets, start=1):
            file = FSInputFile(asset.output_path)
            caption = f"РџСЂРµРІСЊСЋ {index}/{len(context.preview_assets)}{marker_caption}"
            if asset.media_type == "animation":
                await chat_message.answer_animation(animation=file, caption=caption)
            else:
                await chat_message.answer_photo(photo=file, caption=caption)
    else:
        await chat_message.answer("GIF/PNG РїСЂРµРґРїСЂРѕСЃРјРѕС‚СЂ РЅРµ СЃРѕР±СЂР°Р»СЃСЏ, РїРѕРєР°Р·С‹РІР°СЋ С‚РµРєСЃС‚РѕРІСѓСЋ СЃРІРѕРґРєСѓ.")

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

