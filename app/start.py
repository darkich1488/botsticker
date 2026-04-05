from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.callbacks import MainMenuCallback
from app.ui import build_main_menu_text
from app.keyboards.categories import categories_kb
from app.keyboards.main_menu import main_menu_kb
from app.services.pricing_service import PricingService
from app.services.template_repository import TemplateRepository
from app.services.user_repository import InMemoryUserRepository
from app.states import CreatePackState, MainMenuState

router = Router(name="start")
logger = logging.getLogger(__name__)


async def show_main_menu(
    target: Message | CallbackQuery,
    state: FSMContext,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
) -> None:
    if isinstance(target, CallbackQuery):
        message = target.message
        if message is None:
            return
        user_id = target.from_user.id
    else:
        message = target
        if target.from_user is None:
            return
        user_id = target.from_user.id

    profile = user_repository.get_or_create(user_id)
    can_create = pricing_service.estimate_creatable(profile.balance)
    text = build_main_menu_text(balance=profile.balance, can_create=can_create)
    await state.set_state(MainMenuState.idle)

    reply_markup = main_menu_kb(include_admin=user_repository.is_admin(user_id))
    if isinstance(target, CallbackQuery):
        await message.edit_text(text, reply_markup=reply_markup)
        await target.answer()
    else:
        await message.answer(text, reply_markup=reply_markup)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
) -> None:
    await state.clear()
    await show_main_menu(
        target=message,
        state=state,
        user_repository=user_repository,
        pricing_service=pricing_service,
    )


@router.callback_query(MainMenuCallback.filter(F.action == "back_main"))
async def back_main(
    callback: CallbackQuery,
    state: FSMContext,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
) -> None:
    await state.clear()
    await show_main_menu(
        target=callback,
        state=state,
        user_repository=user_repository,
        pricing_service=pricing_service,
    )


@router.callback_query(MainMenuState.idle, MainMenuCallback.filter(F.action == "promo"))
async def promo_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MainMenuState.waiting_promo)
    if callback.message:
        await callback.message.answer("Введите промокод сообщением.")
    await callback.answer()


@router.message(MainMenuState.waiting_promo)
async def promo_message(
    message: Message,
    state: FSMContext,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
) -> None:
    if message.from_user is None:
        return
    code = (message.text or "").strip().upper()
    if code == "DEMO50":
        balance = user_repository.add_balance(message.from_user.id, 50.0)
        await message.answer(f"Промокод применен. Новый баланс: {balance:.2f}")
    else:
        await message.answer("Промокод не найден.")
    await show_main_menu(
        target=message,
        state=state,
        user_repository=user_repository,
        pricing_service=pricing_service,
    )


@router.callback_query(MainMenuState.idle, MainMenuCallback.filter(F.action == "admin_broadcast"))
async def admin_broadcast_start(
    callback: CallbackQuery,
    state: FSMContext,
    user_repository: InMemoryUserRepository,
) -> None:
    if callback.from_user is None:
        return
    if not user_repository.is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    await state.set_state(MainMenuState.waiting_broadcast)
    if callback.message:
        await callback.message.answer("Отправьте текст или фото с подписью для рассылки.")
    await callback.answer()


@router.message(MainMenuState.waiting_broadcast)
async def admin_broadcast_send(
    message: Message,
    state: FSMContext,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
) -> None:
    if message.from_user is None:
        return
    admin_id = message.from_user.id
    if not user_repository.is_admin(admin_id):
        await show_main_menu(
            target=message,
            state=state,
            user_repository=user_repository,
            pricing_service=pricing_service,
        )
        return

    user_ids = [uid for uid in user_repository.list_user_ids() if uid != admin_id]
    if not user_ids:
        await message.answer("Нет получателей для рассылки.")
        await show_main_menu(
            target=message,
            state=state,
            user_repository=user_repository,
            pricing_service=pricing_service,
        )
        return

    sent = 0
    failed = 0

    if message.photo:
        photo_id = message.photo[-1].file_id
        caption = message.caption or ""
        for uid in user_ids:
            try:
                await message.bot.send_photo(uid, photo=photo_id, caption=caption)
                sent += 1
            except Exception:
                failed += 1
    elif message.text:
        text = message.text
        for uid in user_ids:
            try:
                await message.bot.send_message(uid, text)
                sent += 1
            except Exception:
                failed += 1
    else:
        await message.answer("Поддерживается только текст или фото с подписью.")
        return

    await message.answer(f"Рассылка завершена. Отправлено: {sent}, ошибок: {failed}.")
    await show_main_menu(
        target=message,
        state=state,
        user_repository=user_repository,
        pricing_service=pricing_service,
    )


@router.callback_query(MainMenuState.idle, MainMenuCallback.filter(F.action == "new_pack"))
async def new_pack_callback(
    callback: CallbackQuery,
    state: FSMContext,
    template_repository: TemplateRepository,
) -> None:
    if callback.message is None:
        return
    categories = template_repository.get_categories()
    await state.clear()
    await state.set_state(CreatePackState.choosing_category)
    await callback.message.edit_text(
        "Создать стикерпак\n\nВыберите пакет шаблонов:",
        reply_markup=categories_kb(categories),
    )
    await callback.answer()
