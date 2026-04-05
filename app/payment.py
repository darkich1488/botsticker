from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from app.callbacks import PaymentActionCallback, PreviewActionCallback, TemplateActionCallback
from app.keyboards.preview import payment_kb, result_kb
from app.models.payment import PaymentStatus
from app.services.lottie_service import LottieService
from app.services.pack_service import EmojiPackService
from app.services.payment_service import PaymentService
from app.services.preview_service import PreviewService
from app.services.progress_service import ProgressService
from app.services.pricing_service import PricingService
from app.services.template_repository import TemplateRepository
from app.services.user_repository import InMemoryUserRepository
from app.states import CreatePackState, MainMenuState
from app.utils.files import slugify
from app.utils.safe_edit import safe_edit_message

router = Router(name="payment")
logger = logging.getLogger(__name__)

STAGES = (
    "Подготавливаю шаблоны...",
    "Вставляю текст...",
    "Перекрашиваю элементы...",
    "Собираю TGS...",
    "Формирую emoji pack...",
)


@router.callback_query(CreatePackState.preview, PreviewActionCallback.filter(F.action == "to_payment"))
@router.callback_query(CreatePackState.choosing_templates, TemplateActionCallback.filter(F.action == "to_payment"))
async def to_payment(
    callback: CallbackQuery,
    state: FSMContext,
    preview_service: PreviewService,
    payment_service: PaymentService,
    template_repository: TemplateRepository,
    lottie_service: LottieService,
    pack_service: EmojiPackService,
    progress_service: ProgressService,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
) -> None:
    t0 = perf_counter()
    if callback.message is None or callback.from_user is None:
        return

    data = await state.get_data()
    context_id = data.get("preview_context_id")
    context = preview_service.get_context(context_id, user_id=callback.from_user.id) if isinstance(context_id, str) else None
    if context is None:
        category_id = data.get("selected_category_id")
        input_text = data.get("input_text")
        selected_ids = data.get("selected_template_ids", [])
        if not isinstance(category_id, str) or not isinstance(input_text, str) or not selected_ids:
            await callback.answer("Сначала выберите шаблоны и текст.", show_alert=True)
            return
        templates = template_repository.get_templates_by_ids(list(selected_ids))
        if not templates:
            await callback.answer("Не удалось найти выбранные шаблоны.", show_alert=True)
            return
        context = await preview_service.build_preview_context(
            user_id=callback.from_user.id,
            category_id=category_id,
            templates=templates,
            input_text=input_text,
            stroke_color="#111111",
            elements_color="#FFFFFF",
            include_preview_assets=False,
        )
        await state.update_data(
            preview_context_id=context.context_id,
            selected_template_ids=context.selected_template_ids,
        )

    template_count = max(1, len(context.selected_template_ids))
    stars_total = max(1, int(round(context.price)))
    stars_per_sticker = max(1, stars_total // template_count)

    if user_repository.is_admin(callback.from_user.id):
        await callback.answer("Для админа оплата не требуется.")
        try:
            await _run_generation_pipeline(
                trigger_message=callback.message,
                user_id=callback.from_user.id,
                state=state,
                template_repository=template_repository,
                lottie_service=lottie_service,
                preview_service=preview_service,
                pack_service=pack_service,
                progress_service=progress_service,
                user_repository=user_repository,
                pricing_service=pricing_service,
                force_free=True,
            )
        except Exception as exc:
            logger.exception("Pack generation failed user_id=%s error=%s", callback.from_user.id, exc)
            await callback.message.answer("Не удалось завершить создание набора. Попробуйте снова чуть позже.")
        return

    invoice = await payment_service.create_invoice(
        user_id=callback.from_user.id,
        amount=float(stars_total),
        description=f"Emoji pack ({context.category_id})",
    )
    await state.update_data(invoice_id=invoice.id, payment_amount=invoice.amount)
    await state.set_state(CreatePackState.payment)

    try:
        await safe_edit_message(
            message=callback.message,
            text=(
                "Оплата\n\n"
                f"Стикеров: {template_count}\n"
                f"Цена за 1 стикер: {stars_per_sticker} ⭐\n"
                f"Итого: {stars_total} ⭐\n\n"
                "Оплатите инвойс ниже и нажмите «Проверить оплату»."
            ),
            reply_markup=payment_kb(invoice.id),
            logger=logger,
            handler_name="to_payment",
            callback_data=callback.data,
            update_id=callback.id,
        )

        await callback.message.answer_invoice(
            title="Оплата emoji pack",
            description=f"{template_count} стикеров × {stars_per_sticker} ⭐",
            payload=invoice.id,
            currency="XTR",
            prices=[LabeledPrice(label="Emoji pack", amount=stars_total)],
            start_parameter=f"emoji_{invoice.id}",
        )
        await callback.answer()
    finally:
        logger.info(
            "Callback timing handler_name=to_payment callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    await pre_checkout_query.answer(ok=True)


@router.message(CreatePackState.payment, F.successful_payment)
async def successful_payment_message(
    message: Message,
    state: FSMContext,
    payment_service: PaymentService,
    template_repository: TemplateRepository,
    lottie_service: LottieService,
    preview_service: PreviewService,
    pack_service: EmojiPackService,
    progress_service: ProgressService,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
) -> None:
    if message.from_user is None or message.successful_payment is None:
        return

    payload = (message.successful_payment.invoice_payload or "").strip()
    data = await state.get_data()
    expected_invoice_id = str(data.get("invoice_id", "")).strip()
    if expected_invoice_id and payload and payload != expected_invoice_id:
        await message.answer("Оплата получена, но инвойс не совпадает с текущей сессией. Запустите заново.")
        return

    if payload:
        await payment_service.mark_paid(payload)

    await message.answer("Оплата получена. Запускаю генерацию.")
    try:
        await _run_generation_pipeline(
            trigger_message=message,
            user_id=message.from_user.id,
            state=state,
            template_repository=template_repository,
            lottie_service=lottie_service,
            preview_service=preview_service,
            pack_service=pack_service,
            progress_service=progress_service,
            user_repository=user_repository,
            pricing_service=pricing_service,
            force_free=False,
        )
    except Exception as exc:
        logger.exception("Pack generation failed user_id=%s error=%s", message.from_user.id, exc)
        await message.answer("Не удалось завершить создание набора. Попробуйте снова чуть позже.")
        from app.start import show_main_menu

        await show_main_menu(
            target=message,
            state=state,
            user_repository=user_repository,
            pricing_service=pricing_service,
        )


@router.callback_query(CreatePackState.payment, PaymentActionCallback.filter(F.action == "cancel"))
async def payment_cancel(
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
            "Callback timing handler_name=payment_cancel callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


async def _run_generation_pipeline(
    trigger_message: Message,
    user_id: int,
    state: FSMContext,
    template_repository: TemplateRepository,
    lottie_service: LottieService,
    preview_service: PreviewService,
    pack_service: EmojiPackService,
    progress_service: ProgressService,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
    force_free: bool = False,
) -> None:
    data = await state.get_data()

    category_id = data.get("selected_category_id")
    input_text = data.get("input_text")
    pack_title_input = str(data.get("pack_title", "")).strip()
    selected_ids = data.get("selected_template_ids", [])
    context_id = data.get("preview_context_id")

    if not isinstance(category_id, str) or not isinstance(input_text, str) or not selected_ids:
        await trigger_message.answer("Не хватает данных для генерации. Запустите создание заново.")
        from app.start import show_main_menu

        await show_main_menu(
            target=trigger_message,
            state=state,
            user_repository=user_repository,
            pricing_service=pricing_service,
        )
        return

    category = template_repository.get_category(category_id)
    templates = template_repository.get_templates_by_ids(list(selected_ids))
    if not category or not templates:
        await trigger_message.answer("Шаблоны не найдены. Запустите создание заново.")
        from app.start import show_main_menu

        await show_main_menu(
            target=trigger_message,
            state=state,
            user_repository=user_repository,
            pricing_service=pricing_service,
        )
        return

    base_price = pricing_service.calculate_templates_price(len(templates))
    is_free = force_free or user_repository.is_admin(user_id)
    total_price = 0.0 if is_free else base_price
    stroke_color = "#111111"
    elements_color = "#FFFFFF"

    await state.set_state(CreatePackState.generating)
    progress_message = await trigger_message.answer("Запуск генерации...")
    total_stages = len(STAGES)

    logger.info(
        "Generation started user_id=%s category=%s text=%s templates=%s",
        user_id,
        category_id,
        input_text,
        [item.id for item in templates],
    )

    await progress_service.edit_progress(
        progress_message,
        stage_index=1,
        total_stages=total_stages,
        stage_name=STAGES[0],
        percent=0,
        detail=f"Найдено шаблонов: {len(templates)}",
    )
    await asyncio.sleep(0.1)

    processed_by_id: dict[int, dict] = {}
    processed_stats_by_id: dict[int, object] = {}
    enable_recolor = bool(category.supports_recolor)
    for index, template in enumerate(templates, start=1):
        source_json = await asyncio.to_thread(lottie_service.load_lottie_json, template.file_path)
        processed_payload, process_stats = await asyncio.to_thread(
            lottie_service.process_template_data,
            source_data=source_json,
            new_text=input_text,
            stroke_hex=stroke_color,
            elements_hex=elements_color,
            enable_recolor=enable_recolor,
            template_name=template.file_name,
        )
        processed_by_id[template.id] = processed_payload
        processed_stats_by_id[template.id] = process_stats

        layers = processed_payload.get("layers")
        layers_count = len(layers) if isinstance(layers, list) else 0
        glyph_bank_exists = bool(
            isinstance(layers, list)
            and any(
                isinstance(layer, dict) and str(layer.get("nm", "")).strip().lower() == "glyph_bank"
                for layer in layers
            )
        )
        logger.info(
            (
                "Final pipeline payload prepared user_id=%s template=%s "
                "text_keyframes=%s fill=%s/%s stroke=%s/%s skipped=%s "
                "glyph_bank_exists=%s layers_count=%s"
            ),
            user_id,
            template.file_name,
            process_stats.text_keyframes_updated,
            process_stats.fill_nodes_recolored,
            process_stats.fill_nodes_found,
            process_stats.stroke_nodes_recolored,
            process_stats.stroke_nodes_found,
            process_stats.skipped_color_nodes,
            glyph_bank_exists,
            layers_count,
        )

        percent = int(index / len(templates) * 100)
        await progress_service.edit_progress(
            progress_message,
            stage_index=2,
            total_stages=total_stages,
            stage_name=STAGES[1],
            percent=percent,
            detail=f"{index}/{len(templates)} {template.file_name} | замен: {process_stats.text_keyframes_updated}",
        )

    if not enable_recolor:
        logger.info(
            "Recolor stage skipped user_id=%s category=%s reason=supports_recolor_false",
            user_id,
            category.id,
        )
    for index, template in enumerate(templates, start=1):
        stats = processed_stats_by_id[template.id]
        percent = int(index / len(templates) * 100)
        if enable_recolor:
            detail = (
                f"{index}/{len(templates)} {template.file_name} | "
                f"fill={stats.fill_nodes_recolored}, "
                f"stroke={stats.stroke_nodes_recolored}, "
                f"skipped={stats.skipped_color_nodes}"
            )
        else:
            detail = (
                f"{index}/{len(templates)} {template.file_name} | "
                f"shapes=off, text_fc={stats.text_fill_colors_updated}, "
                f"text_sc={stats.text_stroke_colors_updated}"
            )
        await progress_service.edit_progress(
            progress_message,
            stage_index=3,
            total_stages=total_stages,
            stage_name=STAGES[2],
            percent=percent,
            detail=detail,
        )

    emoji_files: list[tuple[str, bytes]] = []
    for index, template in enumerate(templates, start=1):
        payload = processed_by_id[template.id]
        layers = payload.get("layers")
        layers_count = len(layers) if isinstance(layers, list) else 0
        glyph_bank_exists = bool(
            isinstance(layers, list)
            and any(
                isinstance(layer, dict) and str(layer.get("nm", "")).strip().lower() == "glyph_bank"
                for layer in layers
            )
        )
        logger.info(
            "Final TGS prebuild user_id=%s template=%s glyph_bank layers removed count=%s final layers count before build=%s glyph_bank_exists_before_build=%s",
            user_id,
            template.file_name,
            0 if glyph_bank_exists else 1,
            layers_count,
            glyph_bank_exists,
        )
        tgs_bytes = await asyncio.to_thread(lottie_service.build_tgs, payload)
        tgs_name = f"{Path(template.file_name).stem}.tgs"
        emoji_files.append((tgs_name, tgs_bytes))
        percent = int(index / len(templates) * 100)
        await progress_service.edit_progress(
            progress_message,
            stage_index=4,
            total_stages=total_stages,
            stage_name=STAGES[3],
            percent=percent,
            detail=f"{index}/{len(templates)} {tgs_name}",
        )

    base_title = pack_title_input or input_text
    pack_title = f"{base_title} @Hep_kerstickbot".strip()
    safe_title = slugify(pack_title, max_len=32)
    metadata = {
        "created_at": datetime.utcnow().isoformat(),
        "category_id": category.id,
        "input_text": input_text,
        "safe_title": safe_title,
        "paid_stars": str(int(round(total_price))),
    }

    try:
        pack_result = await pack_service.create_pack(
            user_id=user_id,
            title=pack_title,
            emoji_files=emoji_files,
            metadata=metadata,
        )
    except Exception:
        logger.error(
            "Pack creation failed user_id=%s title=%s",
            user_id,
            pack_title,
            exc_info=True,
        )
        await trigger_message.answer(
            "Не удалось создать emoji pack в Telegram. Проверьте права бота и попробуйте снова."
        )
        if isinstance(context_id, str):
            preview_service.release_context(context_id)
        from app.start import show_main_menu

        await show_main_menu(
            target=trigger_message,
            state=state,
            user_repository=user_repository,
            pricing_service=pricing_service,
        )
        return

    await progress_service.edit_progress(
        progress_message,
        stage_index=5,
        total_stages=total_stages,
        stage_name=STAGES[4],
        percent=100,
        detail="✅ Готово",
    )

    user_repository.add_pack(user_id, pack_result)

    logger.info(
        "Generation completed user_id=%s pack_id=%s count=%s",
        user_id,
        pack_result.pack_id,
        pack_result.items_count,
    )

    payment_line = "⭐ Оплачено: бесплатно (admin)" if total_price == 0 else f"⭐ Оплачено: {int(round(total_price))}"
    final_text = (
        "🎉 Ваш стикерпак готов!\n\n"
        f"📦 Создано стикеров: {pack_result.items_count}\n"
        f"📝 Текст: {input_text}\n"
        f"{payment_line}\n\n"
        f"🔗 {pack_result.addemoji_link}\n\n"
        "Нажмите на ссылку, чтобы добавить стикеры в Telegram."
    )
    await trigger_message.answer(final_text, reply_markup=result_kb(pack_result.public_link))

    if isinstance(context_id, str):
        preview_service.release_context(context_id)

    from app.start import show_main_menu

    await show_main_menu(
        target=trigger_message,
        state=state,
        user_repository=user_repository,
        pricing_service=pricing_service,
    )


@router.callback_query(CreatePackState.payment, PaymentActionCallback.filter(F.action == "check"))
async def payment_check(
    callback: CallbackQuery,
    callback_data: PaymentActionCallback,
    state: FSMContext,
    payment_service: PaymentService,
    template_repository: TemplateRepository,
    lottie_service: LottieService,
    preview_service: PreviewService,
    pack_service: EmojiPackService,
    progress_service: ProgressService,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
) -> None:
    t0 = perf_counter()
    if callback.from_user is None or callback.message is None:
        return

    status = await payment_service.check_payment(
        invoice_id=callback_data.invoice_id,
        user_id=callback.from_user.id,
    )
    if status != PaymentStatus.PAID:
        await callback.answer("Оплата еще не подтверждена.", show_alert=True)
        return

    await callback.answer("Оплата подтверждена. Запускаю генерацию.")
    try:
        await _run_generation_pipeline(
            trigger_message=callback.message,
            user_id=callback.from_user.id,
            state=state,
            template_repository=template_repository,
            lottie_service=lottie_service,
            preview_service=preview_service,
            pack_service=pack_service,
            progress_service=progress_service,
            user_repository=user_repository,
            pricing_service=pricing_service,
            force_free=False,
        )
    except Exception as exc:
        logger.exception("Pack generation failed user_id=%s error=%s", callback.from_user.id, exc)
        await callback.message.answer("Не удалось завершить создание набора. Попробуйте снова чуть позже.")
        from app.start import show_main_menu

        await show_main_menu(
            target=callback,
            state=state,
            user_repository=user_repository,
            pricing_service=pricing_service,
        )
    finally:
        logger.info(
            "Callback timing handler_name=payment_check callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.callback_query(CreatePackState.generating)
async def generating_block(callback: CallbackQuery) -> None:
    await callback.answer("Генерация уже выполняется, дождитесь завершения.")
