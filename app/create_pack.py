from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from time import perf_counter

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from app.callbacks import CategoryCallback, TemplateActionCallback, TemplatePageCallback, TemplateToggleCallback
from app.config import Settings
from app.ui import build_template_selection_text
from app.keyboards.selection import template_selection_kb
from app.services.pricing_service import PricingService
from app.services.template_repository import TemplateRepository
from app.services.user_repository import InMemoryUserRepository
from app.states import CreatePackState
from app.utils.safe_edit import safe_edit_message

router = Router(name="create_pack")
logger = logging.getLogger(__name__)
_TEMPLATE_GUIDE_IMAGE_PATH = Path(__file__).resolve().parent / "assets" / "emoji_picker_guide.png"


async def _safe_delete_message(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        return


async def _delete_prompt_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    prompt_message_id = data.get("flow_prompt_message_id")
    if not isinstance(prompt_message_id, int):
        return
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
    except Exception:
        pass
    await state.update_data(flow_prompt_message_id=None)


async def _delete_prompt_message_by_id(message: Message, prompt_message_id: int) -> None:
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_message_id)
    except Exception:
        pass


async def _send_prompt(message: Message, state: FSMContext, text: str) -> None:
    await _delete_prompt_message(message, state)
    sent = await message.answer(text)
    await state.update_data(flow_prompt_message_id=sent.message_id)


async def _send_template_guide_once(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if bool(data.get("template_guide_sent")):
        return

    if not _TEMPLATE_GUIDE_IMAGE_PATH.is_file():
        logger.warning("Template guide image not found path=%s", _TEMPLATE_GUIDE_IMAGE_PATH)
        await state.update_data(template_guide_sent=True)
        return

    try:
        await message.answer_photo(FSInputFile(str(_TEMPLATE_GUIDE_IMAGE_PATH)))
        logger.info("Template guide image sent path=%s", _TEMPLATE_GUIDE_IMAGE_PATH)
    except Exception:
        logger.warning("Template guide image send failed path=%s", _TEMPLATE_GUIDE_IMAGE_PATH, exc_info=True)
        return
    await state.update_data(template_guide_sent=True)


async def show_template_selection_screen(
    target: Message | CallbackQuery,
    state: FSMContext,
    template_repository: TemplateRepository,
    pricing_service: PricingService,
    settings: Settings,
) -> None:
    data = await state.get_data()
    category_id = data.get("selected_category_id")
    if not isinstance(category_id, str):
        if isinstance(target, CallbackQuery):
            await target.answer("Сначала выберите пакет.", show_alert=True)
        return

    category = template_repository.get_category(category_id)
    if category is None:
        if isinstance(target, CallbackQuery):
            await target.answer("Категория не найдена.", show_alert=True)
        return

    selected_ids = set(data.get("selected_template_ids", []))
    page = int(data.get("current_page", 1))
    page_items, current_page, total_pages, total_count = template_repository.get_templates_page(
        category_id=category_id,
        page=page,
        per_page=settings.templates_per_page,
    )
    await state.update_data(current_page=current_page)
    price = pricing_service.calculate_templates_price(len(selected_ids))

    text = build_template_selection_text(
        category=category,
        current_page=current_page,
        total_pages=total_pages,
        selected_count=len(selected_ids),
        total_templates=total_count,
        current_price=price,
    )
    kb = template_selection_kb(
        templates=page_items,
        selected_template_ids=selected_ids,
        current_page=current_page,
        total_pages=total_pages,
        supports_recolor=category.supports_recolor,
    )

    if isinstance(target, CallbackQuery):
        if target.message:
            await safe_edit_message(
                message=target.message,
                text=text,
                reply_markup=kb,
                logger=logger,
                handler_name="show_template_selection_screen",
                callback_data=target.data,
                update_id=target.id,
            )
        await target.answer()
    else:
        await _send_template_guide_once(message=target, state=state)
        await target.answer(text, reply_markup=kb)


@router.callback_query(CreatePackState.choosing_category, CategoryCallback.filter())
async def choose_category(
    callback: CallbackQuery,
    callback_data: CategoryCallback,
    state: FSMContext,
    template_repository: TemplateRepository,
) -> None:
    t0 = perf_counter()
    try:
        category = template_repository.get_category(callback_data.category_id)
        if category is None:
            await callback.answer("Пакет не найден.", show_alert=True)
            return

        if category.id == "recolor":
            await callback.answer("Раздел «Перекрас» в разработке, очень скоро.", show_alert=True)
            return

        await state.update_data(
            selected_category_id=category.id,
            input_text="",
            pack_title="",
            selected_template_ids=[],
            current_page=1,
            preview_context_id=None,
            random_mode=False,
            awaiting_page_input=False,
            template_guide_sent=False,
            flow_prompt_message_id=callback.message.message_id if callback.message else None,
        )
        await state.set_state(CreatePackState.waiting_text)

        if callback.message:
            await safe_edit_message(
                message=callback.message,
                text="Введите текст для стикеров.",
                logger=logger,
                handler_name="choose_category",
                callback_data=callback.data,
                update_id=callback.id,
            )
        await callback.answer()
    finally:
        logger.info(
            "Callback timing handler_name=choose_category callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.message(CreatePackState.waiting_text)
async def receive_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст пустой. Отправьте текст для эмодзи.")
        return
    if len(text) > 20:
        await message.answer("Текст слишком длинный. Максимум 20 символов.")
        return

    await state.update_data(input_text=text)
    await state.set_state(CreatePackState.waiting_pack_title)
    await _safe_delete_message(message)
    await _send_prompt(message, state, "Введите название стикерпака.")


@router.message(CreatePackState.waiting_pack_title)
async def receive_pack_title(
    message: Message,
    state: FSMContext,
    template_repository: TemplateRepository,
    pricing_service: PricingService,
    settings: Settings,
) -> None:
    t0 = perf_counter()
    pack_title = (message.text or "").strip()
    if not pack_title:
        await message.answer("Название не может быть пустым. Введите название стикерпака.")
        return
    if len(pack_title) > 40:
        await message.answer("Название слишком длинное. Максимум 40 символов.")
        return

    data = await state.get_data()
    prompt_message_id = data.get("flow_prompt_message_id")
    await state.update_data(pack_title=pack_title, flow_prompt_message_id=None)
    await state.set_state(CreatePackState.choosing_templates)

    # Avoid UI freeze: cleanup messages in background while immediately rendering template picker.
    asyncio.create_task(_safe_delete_message(message))
    if isinstance(prompt_message_id, int):
        asyncio.create_task(_delete_prompt_message_by_id(message, prompt_message_id))

    await show_template_selection_screen(
        target=message,
        state=state,
        template_repository=template_repository,
        pricing_service=pricing_service,
        settings=settings,
    )
    logger.info(
        "Receive pack title done handler_name=receive_pack_title duration_ms=%s",
        int((perf_counter() - t0) * 1000),
    )


@router.callback_query(CreatePackState.choosing_templates, TemplateToggleCallback.filter())
async def toggle_template(
    callback: CallbackQuery,
    callback_data: TemplateToggleCallback,
    state: FSMContext,
    template_repository: TemplateRepository,
    pricing_service: PricingService,
    settings: Settings,
) -> None:
    t0 = perf_counter()
    try:
        data = await state.get_data()
        selected_ids = set(data.get("selected_template_ids", []))
        template = template_repository.get_template_by_id(callback_data.template_id)
        if template is None:
            await callback.answer("Шаблон не найден.", show_alert=True)
            return

        if callback_data.template_id in selected_ids:
            selected_ids.remove(callback_data.template_id)
        else:
            selected_ids.add(callback_data.template_id)

        await state.update_data(selected_template_ids=sorted(selected_ids))
        await show_template_selection_screen(
            target=callback,
            state=state,
            template_repository=template_repository,
            pricing_service=pricing_service,
            settings=settings,
        )
    finally:
        logger.info(
            "Callback timing handler_name=toggle_template callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.callback_query(CreatePackState.choosing_templates, TemplatePageCallback.filter())
async def change_page(
    callback: CallbackQuery,
    callback_data: TemplatePageCallback,
    state: FSMContext,
    template_repository: TemplateRepository,
    pricing_service: PricingService,
    settings: Settings,
) -> None:
    t0 = perf_counter()
    try:
        await state.update_data(current_page=callback_data.page)
        await show_template_selection_screen(
            target=callback,
            state=state,
            template_repository=template_repository,
            pricing_service=pricing_service,
            settings=settings,
        )
    finally:
        logger.info(
            "Callback timing handler_name=change_page callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.callback_query(CreatePackState.choosing_templates, TemplateActionCallback.filter(F.action == "random_here"))
async def random_here(
    callback: CallbackQuery,
    state: FSMContext,
    template_repository: TemplateRepository,
    pricing_service: PricingService,
    settings: Settings,
) -> None:
    t0 = perf_counter()
    try:
        data = await state.get_data()
        category_id = data.get("selected_category_id")
        if not isinstance(category_id, str):
            await callback.answer("Категория не выбрана.", show_alert=True)
            return
        random_templates = template_repository.random_templates(category_id=category_id, count=None)
        selected_ids = [item.id for item in random_templates]
        await state.update_data(selected_template_ids=selected_ids)
        await callback.answer(f"Выбрано случайно: {len(selected_ids)}")
        await show_template_selection_screen(
            target=callback,
            state=state,
            template_repository=template_repository,
            pricing_service=pricing_service,
            settings=settings,
        )
    finally:
        logger.info(
            "Callback timing handler_name=random_here callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.callback_query(CreatePackState.choosing_templates, TemplateActionCallback.filter(F.action == "select_all"))
async def select_all_templates(
    callback: CallbackQuery,
    state: FSMContext,
    template_repository: TemplateRepository,
    pricing_service: PricingService,
    settings: Settings,
) -> None:
    t0 = perf_counter()
    try:
        data = await state.get_data()
        category_id = data.get("selected_category_id")
        if not isinstance(category_id, str):
            await callback.answer("Категория не выбрана.", show_alert=True)
            return
        selected_ids = [item.id for item in template_repository.get_templates_by_category(category_id)]
        await state.update_data(selected_template_ids=selected_ids)
        await show_template_selection_screen(
            target=callback,
            state=state,
            template_repository=template_repository,
            pricing_service=pricing_service,
            settings=settings,
        )
    finally:
        logger.info(
            "Callback timing handler_name=select_all_templates callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.callback_query(CreatePackState.choosing_templates, TemplateActionCallback.filter(F.action == "page_pick"))
async def page_pick_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    t0 = perf_counter()
    try:
        await state.update_data(awaiting_page_input=True)
        if callback.message:
            await callback.message.answer("Введите номер страницы сообщением.")
        await callback.answer()
    finally:
        logger.info(
            "Callback timing handler_name=page_pick_prompt callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.callback_query(CreatePackState.choosing_templates, TemplateActionCallback.filter(F.action == "back_mode"))
async def back_to_main_menu(
    callback: CallbackQuery,
    state: FSMContext,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
) -> None:
    t0 = perf_counter()
    try:
        from app.start import show_main_menu

        await show_main_menu(
            target=callback,
            state=state,
            user_repository=user_repository,
            pricing_service=pricing_service,
        )
    finally:
        logger.info(
            "Callback timing handler_name=back_to_main_menu callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.callback_query(CreatePackState.choosing_templates, TemplateActionCallback.filter(F.action == "noop"))
async def noop_action(callback: CallbackQuery) -> None:
    t0 = perf_counter()
    try:
        await callback.answer()
    finally:
        logger.info(
            "Callback timing handler_name=noop_action callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.message(CreatePackState.choosing_templates)
async def choosing_templates_message(
    message: Message,
    state: FSMContext,
    template_repository: TemplateRepository,
    pricing_service: PricingService,
    settings: Settings,
) -> None:
    data = await state.get_data()
    raw_text = (message.text or "").strip()
    if data.get("awaiting_page_input"):
        if not raw_text.isdigit():
            await message.answer("Номер страницы должен быть числом.")
            return
        page = int(raw_text)
        await state.update_data(current_page=max(1, page), awaiting_page_input=False)
        await show_template_selection_screen(
            target=message,
            state=state,
            template_repository=template_repository,
            pricing_service=pricing_service,
            settings=settings,
        )
        return

    await message.answer("Используйте кнопки ниже для выбора шаблонов.")

