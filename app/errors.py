from __future__ import annotations

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent

from app.start import show_main_menu
from app.services.pricing_service import PricingService
from app.services.user_repository import InMemoryUserRepository

router = Router(name="errors")
logger = logging.getLogger(__name__)


@router.error()
async def on_error(
    event: ErrorEvent,
    state: FSMContext,
    user_repository: InMemoryUserRepository,
    pricing_service: PricingService,
) -> None:
    logger.exception("Unhandled error: %s", event.exception)
    update = event.update

    callback = getattr(update, "callback_query", None)
    if callback and callback.message:
        await callback.message.answer("Произошла ошибка. Возвращаю вас в главное меню.")
        await show_main_menu(
            target=callback,
            state=state,
            user_repository=user_repository,
            pricing_service=pricing_service,
        )
        return

    message = getattr(update, "message", None)
    if message:
        await message.answer("Произошла ошибка. Возвращаю вас в главное меню.")
        await show_main_menu(
            target=message,
            state=state,
            user_repository=user_repository,
            pricing_service=pricing_service,
        )
