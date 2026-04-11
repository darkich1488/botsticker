from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from time import perf_counter

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, LabeledPrice, Message, PreCheckoutQuery

from app.callbacks import PaymentActionCallback, PreviewActionCallback, TemplateActionCallback
from app.config import Settings
from app.keyboards.preview import payment_kb, result_kb
from app.models.payment import PaymentStatus
from app.preview_helpers import build_blue_preview_collage
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

PROMO_CANCEL_WORDS = {"-", "отмена", "/cancel", "/stop"}

def _compute_invoice_totals(
    *,
    base_price: float,
    template_count: int,
    discount_value: float = 0.0,
) -> tuple[float, int, int, int]:
    safe_base = max(0.0, float(base_price))
    safe_discount = max(0.0, float(discount_value))
    discounted_amount = max(0.0, round(max(0.0, safe_base - safe_discount), 2))
    safe_template_count = max(1, int(template_count))
    base_stars_total = max(0, int(round(safe_base)))
    stars_total = max(0, int(round(discounted_amount)))
    stars_per_sticker = max(1, base_stars_total // safe_template_count) if base_stars_total > 0 else 0
    return discounted_amount, stars_total, stars_per_sticker, base_stars_total


def _normalize_promo_code(raw: str) -> str:
    return raw.strip().upper()


def _build_payment_text(
    *,
    template_count: int,
    stars_per_sticker: int,
    base_stars_total: int,
    stars_total: int,
    discount_stars: int = 0,
    promo_code: str | None = None,
    pay_required: bool = True,
) -> str:
    payment_hint = "Оплатите инвойс ниже и нажмите «Проверить оплату»."
    if not pay_required:
        payment_hint = "Оплата не требуется. Нажмите «Создать набор»."
    lines = [
        "Оплата",
        "",
        f"Стикеров: {template_count}",
        f"Цена за 1 стикер: {stars_per_sticker} ⭐",
        f"Базовая цена: {base_stars_total} ⭐",
    ]
    if discount_stars > 0 and promo_code:
        lines.append(f"Промокод {promo_code}: -{discount_stars} ⭐")
    lines.extend(
        [
            f"Итого к оплате: {stars_total} ⭐",
            "",
            payment_hint,
        ]
    )
    return "\n".join(lines)


def _resolve_promo_discount(
    *,
    raw_code: str,
    settings: Settings,
) -> tuple[str, float] | None:
    promo_code = _normalize_promo_code(raw_code)
    if not promo_code:
        return None
    discount = settings.payment_promo_codes.get(promo_code)
    if discount is None:
        return None
    return promo_code, float(discount)


async def _issue_payment_invoice(
    *,
    target_message: Message,
    state: FSMContext,
    payment_service: PaymentService,
    user_id: int,
    category_id: str | None,
    template_count: int,
    base_price: float,
    edit_existing: bool,
    handler_name: str,
    discount_value: float = 0.0,
    promo_code: str | None = None,
    callback_data: str | None = None,
    update_id: str | None = None,
) -> None:
    _, stars_total, stars_per_sticker, base_stars_total = _compute_invoice_totals(
        base_price=base_price,
        template_count=template_count,
        discount_value=discount_value,
    )
    discount_stars = max(0, base_stars_total - stars_total)
    pay_required = stars_total > 0
    invoice_id = "FREE_INVOICE"
    if pay_required:
        invoice = await payment_service.create_invoice(
            user_id=user_id,
            amount=float(stars_total),
            description=f"Emoji pack ({category_id if isinstance(category_id, str) else 'unknown'})",
        )
        invoice_id = invoice.id
    await state.update_data(
        invoice_id=invoice_id,
        payment_amount=float(stars_total),
        payment_base_price=float(base_price),
        payment_discount_value=float(discount_value),
        payment_promo_code=promo_code or "",
        payment_is_free=not pay_required,
        awaiting_payment_promo=False,
    )
    payment_text = _build_payment_text(
        template_count=template_count,
        stars_per_sticker=stars_per_sticker,
        base_stars_total=base_stars_total,
        stars_total=stars_total,
        discount_stars=discount_stars,
        promo_code=promo_code,
        pay_required=pay_required,
    )
    if edit_existing:
        await safe_edit_message(
            message=target_message,
            text=payment_text,
            reply_markup=payment_kb(invoice_id, pay_required=pay_required),
            logger=logger,
            handler_name=handler_name,
            callback_data=callback_data,
            update_id=update_id,
        )
    else:
        await target_message.answer(
            payment_text,
            reply_markup=payment_kb(invoice_id, pay_required=pay_required),
        )

    if pay_required:
        await target_message.answer_invoice(
            title="Оплата emoji pack",
            description=f"{template_count} стикеров × {stars_per_sticker} ⭐",
            payload=invoice_id,
            currency="XTR",
            prices=[LabeledPrice(label="Emoji pack", amount=stars_total)],
            start_parameter=f"emoji_{invoice_id}",
        )


async def _send_preview_before_payment(
    *,
    target_message: Message,
    state: FSMContext,
    preview_service: PreviewService,
    template_repository: TemplateRepository,
    user_id: int,
    category_id: str,
    templates: list,
    input_text: str,
    stroke_color: str = "#111111",
    elements_color: str = "#FFFFFF",
) -> None:
    data = await state.get_data()
    context_id = data.get("preview_context_id")
    context = preview_service.get_context(context_id, user_id=user_id) if isinstance(context_id, str) else None

    if context is None or not context.preview_assets:
        try:
            context = await preview_service.build_preview_context(
                user_id=user_id,
                category_id=category_id,
                templates=templates,
                input_text=input_text,
                stroke_color=stroke_color,
                elements_color=elements_color,
                include_preview_assets=True,
            )
            await state.update_data(
                preview_context_id=context.context_id,
                selected_template_ids=context.selected_template_ids,
            )
        except Exception as exc:
            logger.warning("Preview before payment failed user_id=%s error=%s", user_id, exc)
            return

    if not context.preview_assets:
        return

    collage_path = build_blue_preview_collage(preview_assets=context.preview_assets, user_id=user_id)
    try:
        if collage_path:
            await target_message.answer_photo(photo=FSInputFile(collage_path), caption="Пример")
            Path(collage_path).unlink(missing_ok=True)
        else:
            await target_message.answer_photo(photo=FSInputFile(context.preview_assets[0].output_path), caption="Пример")
    except Exception as exc:
        logger.warning("Preview photo send failed user_id=%s error=%s", user_id, exc)


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
    try:
        await callback.answer()
    except TelegramBadRequest as exc:
        message = str(exc).lower()
        if "query is too old" in message or "query id is invalid" in message:
            logger.info("Skip stale callback answer handler_name=to_payment update_id=%s", callback.id)
        else:
            raise

    data = await state.get_data()
    context_id = data.get("preview_context_id")
    context = preview_service.get_context(context_id, user_id=callback.from_user.id) if isinstance(context_id, str) else None
    category_id = data.get("selected_category_id")
    input_text = data.get("input_text")
    selected_template_ids: list[int]
    templates: list
    computed_price: float
    if context is None:
        selected_ids = data.get("selected_template_ids", [])
        if not isinstance(category_id, str) or not isinstance(input_text, str) or not selected_ids:
            await callback.answer("Сначала выберите шаблоны и текст.", show_alert=True)
            return
        templates = template_repository.get_templates_by_ids(list(selected_ids))
        if not templates:
            await callback.answer("Не удалось найти выбранные шаблоны.", show_alert=True)
            return
        selected_template_ids = [item.id for item in templates]
        computed_price = pricing_service.calculate_templates_price(len(selected_template_ids))
        await state.update_data(
            selected_template_ids=selected_template_ids,
        )
        logger.info(
            "to_payment fast path category=%s templates=%s price=%s context_reused=False",
            category_id,
            len(selected_template_ids),
            computed_price,
        )
    else:
        if not isinstance(category_id, str):
            category_id = context.category_id
        if not isinstance(input_text, str):
            input_text = context.input_text
        selected_template_ids = list(context.selected_template_ids)
        templates = template_repository.get_templates_by_ids(selected_template_ids)
        if not templates:
            await callback.answer("Не удалось найти выбранные шаблоны.", show_alert=True)
            return
        computed_price = float(context.price)
        logger.info(
            "to_payment context path category=%s templates=%s price=%s context_reused=True",
            category_id,
            len(selected_template_ids),
            computed_price,
        )

    await state.update_data(selected_template_ids=selected_template_ids)
    template_count = max(1, len(selected_template_ids))
    promo_code = _normalize_promo_code(str(data.get("payment_promo_code", "")))
    discount_value = float(data.get("payment_discount_value") or 0.0) if promo_code else 0.0

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

    if isinstance(category_id, str) and isinstance(input_text, str):
        await _send_preview_before_payment(
            target_message=callback.message,
            state=state,
            preview_service=preview_service,
            template_repository=template_repository,
            user_id=callback.from_user.id,
            category_id=category_id,
            templates=templates,
            input_text=input_text,
        )

    await state.set_state(CreatePackState.payment)

    try:
        await _issue_payment_invoice(
            target_message=callback.message,
            state=state,
            payment_service=payment_service,
            user_id=callback.from_user.id,
            category_id=category_id if isinstance(category_id, str) else None,
            template_count=template_count,
            base_price=float(computed_price),
            discount_value=discount_value,
            promo_code=promo_code or None,
            edit_existing=True,
            handler_name="to_payment",
            callback_data=callback.data,
            update_id=callback.id,
        )
    finally:
        logger.info(
            "Callback timing handler_name=to_payment callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.callback_query(CreatePackState.payment, PaymentActionCallback.filter(F.action == "promo"))
async def payment_promo_start(
    callback: CallbackQuery,
    callback_data: PaymentActionCallback,
    state: FSMContext,
    settings: Settings,
) -> None:
    t0 = perf_counter()
    if callback.from_user is None or callback.message is None:
        return
    try:
        data = await state.get_data()
        expected_invoice_id = str(data.get("invoice_id", "")).strip()
        if expected_invoice_id and callback_data.invoice_id != expected_invoice_id:
            await callback.answer("Используйте кнопку из последнего инвойса.", show_alert=True)
            return
        if not settings.payment_promo_codes:
            await callback.answer("Промокоды сейчас отключены.", show_alert=True)
            return
        await state.update_data(awaiting_payment_promo=True)
        await callback.message.answer("Введите промокод сообщением.\nДля отмены отправьте «-».")
        await callback.answer()
    finally:
        logger.info(
            "Callback timing handler_name=payment_promo_start callback_data=%s update_id=%s duration_ms=%s",
            callback.data,
            callback.id,
            int((perf_counter() - t0) * 1000),
        )


@router.message(CreatePackState.payment, F.text)
async def payment_promo_message(
    message: Message,
    state: FSMContext,
    settings: Settings,
    payment_service: PaymentService,
    user_repository: InMemoryUserRepository,
) -> None:
    if message.from_user is None:
        return
    data = await state.get_data()
    if not bool(data.get("awaiting_payment_promo")):
        return

    raw_text = str(message.text or "").strip()
    if not raw_text:
        await message.answer("Введите промокод текстом.")
        return

    if raw_text.lower() in PROMO_CANCEL_WORDS:
        await state.update_data(awaiting_payment_promo=False)
        await message.answer("Ввод промокода отменён.")
        return

    resolved = _resolve_promo_discount(raw_code=raw_text, settings=settings)
    if resolved is None:
        await message.answer("Промокод не найден. Попробуйте ещё раз или отправьте «-» для отмены.")
        return

    promo_code, discount_value = resolved
    status, _ = user_repository.consume_limited_promo(
        user_id=message.from_user.id,
        code=promo_code,
        max_uses=settings.payment_promo_max_uses,
    )
    if status == "already_used":
        await message.answer("Вы уже использовали этот промокод.")
        return
    if status == "limit_reached":
        await message.answer("Лимит активаций этого промокода исчерпан.")
        return

    selected_template_ids = data.get("selected_template_ids", [])
    template_count = max(1, len(selected_template_ids)) if isinstance(selected_template_ids, list) else 1
    category_id = data.get("selected_category_id")
    base_price = float(data.get("payment_base_price") or 0.0)

    await _issue_payment_invoice(
        target_message=message,
        state=state,
        payment_service=payment_service,
        user_id=message.from_user.id,
        category_id=category_id if isinstance(category_id, str) else None,
        template_count=template_count,
        base_price=base_price,
        discount_value=discount_value,
        promo_code=promo_code,
        edit_existing=False,
        handler_name="payment_promo_message",
        update_id=str(message.message_id),
    )
    await message.answer(f"Промокод {promo_code} применён. Инвойс обновлён.")


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
    paid_from_state = float(data.get("payment_amount") or 0.0)
    total_price = 0.0 if is_free else max(0.0, paid_from_state or base_price)
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
    data = await state.get_data()
    expected_invoice_id = str(data.get("invoice_id", "")).strip()
    if expected_invoice_id and callback_data.invoice_id != expected_invoice_id:
        await callback.answer("Используйте кнопку из последнего инвойса.", show_alert=True)
        return
    payment_amount = float(data.get("payment_amount") or 0.0)
    if payment_amount <= 0:
        await callback.answer("Оплата не требуется. Запускаю генерацию.")
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
