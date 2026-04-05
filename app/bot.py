from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import ensure_runtime_dirs, load_settings
from app import create_pack, errors, payment, preview, start
from app.services.lottie_service import LottieService
from app.services.pack_service import EmojiPackService
from app.services.payment_service import FakePaymentService
from app.services.preview_render_service import PreviewRenderService
from app.services.preview_service import PreviewService
from app.services.progress_service import ProgressService
from app.services.telegram_pack_provider import TelegramPackProvider
from app.services.pricing_service import PricingService
from app.services.template_repository import TemplateRepository
from app.services.user_repository import InMemoryUserRepository
from app.utils.logger import setup_logging


async def main() -> None:
    settings = load_settings()
    ensure_runtime_dirs(settings)
    setup_logging(settings.log_level)
    logger = logging.getLogger("bot")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    template_repository = TemplateRepository(settings=settings)
    pricing_service = PricingService(price_per_template=settings.price_per_template)
    user_repository = InMemoryUserRepository(admin_user_ids=set(settings.admin_user_ids))
    payment_service = FakePaymentService()
    lottie_service = LottieService()
    preview_render_service = PreviewRenderService(settings=settings)
    preview_service = PreviewService(
        lottie_service=lottie_service,
        preview_render_service=preview_render_service,
        pricing_service=pricing_service,
    )
    pack_service = EmojiPackService(provider=TelegramPackProvider(bot=bot))
    progress_service = ProgressService()

    dp["settings"] = settings
    dp["template_repository"] = template_repository
    dp["pricing_service"] = pricing_service
    dp["user_repository"] = user_repository
    dp["payment_service"] = payment_service
    dp["lottie_service"] = lottie_service
    dp["preview_render_service"] = preview_render_service
    dp["preview_service"] = preview_service
    dp["pack_service"] = pack_service
    dp["progress_service"] = progress_service

    dp.include_router(start.router)
    dp.include_router(create_pack.router)
    dp.include_router(preview.router)
    dp.include_router(payment.router)
    dp.include_router(errors.router)

    logger.info("Bot started polling")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
