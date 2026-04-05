from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import socket
import uuid
from contextlib import suppress

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


def _acquire_single_instance_lock(bot_token: str, logger: logging.Logger) -> tuple[socket.socket, int]:
    token_hash = int(hashlib.sha1(bot_token.encode("utf-8")).hexdigest()[:8], 16)
    lock_port = 20000 + (token_hash % 20000)
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        lock_socket.bind(("127.0.0.1", lock_port))
        lock_socket.listen(1)
    except OSError as exc:
        with suppress(Exception):
            lock_socket.close()
        logger.error(
            "Polling lock failed lock_port=%s exception_type=%s",
            lock_port,
            type(exc).__name__,
        )
        raise RuntimeError("another polling instance is already running on this host") from exc
    return lock_socket, lock_port


async def main() -> None:
    settings = load_settings()
    ensure_runtime_dirs(settings)
    setup_logging(settings.log_level)
    logger = logging.getLogger("bot")
    instance_id = os.getenv("RAILWAY_REPLICA_ID") or uuid.uuid4().hex[:8]
    lock_socket: socket.socket | None = None
    lock_port: int | None = None
    polling_stop_reason = "normal"

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

    lock_socket, lock_port = _acquire_single_instance_lock(settings.bot_token, logger)
    me = await bot.get_me()
    logger.info(
        "Polling start instance_id=%s pid=%s hostname=%s bot_id=%s entrypoint=%s lock_port=%s",
        instance_id,
        os.getpid(),
        socket.gethostname(),
        me.id,
        "python -m app.bot",
        lock_port,
    )
    try:
        await dp.start_polling(bot)
    except Exception as exc:
        polling_stop_reason = "exception"
        logger.exception(
            "Polling stopped with error instance_id=%s exception_type=%s",
            instance_id,
            type(exc).__name__,
        )
        raise
    finally:
        logger.info(
            "Polling stopped instance_id=%s polling_stop_reason=%s",
            instance_id,
            polling_stop_reason,
        )
        if lock_socket is not None:
            with suppress(Exception):
                lock_socket.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
