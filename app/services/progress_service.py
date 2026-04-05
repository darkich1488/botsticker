from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Callable, TypeVar

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

DEFAULT_LOG_FILE = "bot_debug.log"
T = TypeVar("T")


def _ensure_file_and_console_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_emoji_bot_logging_ready", False):
        return
    enable_file_log = os.getenv("BOT_FILE_LOG", "0").strip().lower() in {"1", "true", "yes"}

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    has_console = any(
        isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
        for handler in root.handlers
    )
    if not has_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    has_file = any(
        isinstance(handler, logging.FileHandler)
        and Path(getattr(handler, "baseFilename", "")).name == DEFAULT_LOG_FILE
        for handler in root.handlers
    )
    if enable_file_log and not has_file:
        file_handler = logging.FileHandler(DEFAULT_LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    setattr(root, "_emoji_bot_logging_ready", True)


def calculate_percent(current_step: int, total_steps: int) -> int:
    if total_steps <= 0:
        return 0
    bounded_step = max(0, min(current_step, total_steps))
    return int(round((bounded_step / total_steps) * 100))


def build_progress_bar(percent: int, width: int = 10) -> str:
    safe_percent = max(0, min(percent, 100))
    filled = int(round((safe_percent / 100) * width))
    filled = min(width, max(0, filled))
    return f"{'█' * filled}{'░' * (width - filled)} {safe_percent}%"


class ProgressService:
    def __init__(self) -> None:
        _ensure_file_and_console_logging()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._last_text_cache: dict[tuple[int, int], str] = {}
        self._logger.info("ProgressService initialized")

    @staticmethod
    def format_progress_text(
        stage_index: int,
        total_stages: int,
        stage_name: str,
        percent: int,
        detail: str | None = None,
    ) -> str:
        lines = [
            f"{stage_index}/{total_stages} {stage_name}",
            build_progress_bar(percent),
        ]
        if detail:
            lines.append(detail)
        return "\n".join(lines)

    async def edit_progress(
        self,
        message: Message,
        stage_index: int,
        total_stages: int,
        stage_name: str,
        percent: int,
        detail: str | None = None,
    ) -> bool:
        # Normalize to stage-based progress to avoid 100% on every step.
        effective_percent = calculate_percent(stage_index, total_stages)
        text = self.format_progress_text(
            stage_index=stage_index,
            total_stages=total_stages,
            stage_name=stage_name,
            percent=effective_percent,
            detail=detail,
        )
        message_key = (message.chat.id, message.message_id)
        previous_text = self._last_text_cache.get(message_key)
        if previous_text == text:
            self._logger.debug(
                "Progress skip unchanged stage=%s current_step=%s total_steps=%s "
                "percent=%s detail=%s chat_id=%s message_id=%s",
                stage_name,
                stage_index,
                total_stages,
                effective_percent,
                detail or "",
                message.chat.id,
                message.message_id,
            )
            return False

        self._logger.info(
            "Progress step stage=%s current_step=%s total_steps=%s percent=%s "
            "detail=%s chat_id=%s message_id=%s",
            stage_name,
            stage_index,
            total_stages,
            effective_percent,
            detail or "",
            message.chat.id,
            message.message_id,
        )
        try:
            await message.edit_text(text)
            self._last_text_cache[message_key] = text
            self._logger.info(
                "Progress update success chat_id=%s message_id=%s",
                message.chat.id,
                message.message_id,
            )
            await asyncio.sleep(0)
            return True
        except TelegramBadRequest as exc:
            exc_text = str(exc).lower()
            if "message is not modified" in exc_text:
                self._last_text_cache[message_key] = text
                self._logger.debug(
                    "Progress edit ignored (not modified) chat_id=%s message_id=%s",
                    message.chat.id,
                    message.message_id,
                )
                return False

            self._logger.error(
                "Progress edit_text failed chat_id=%s message_id=%s, "
                "fallback to edit_message_text",
                message.chat.id,
                message.message_id,
                exc_info=True,
            )
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    text=text,
                )
                self._last_text_cache[message_key] = text
                self._logger.info(
                    "Progress fallback update success chat_id=%s message_id=%s",
                    message.chat.id,
                    message.message_id,
                )
                await asyncio.sleep(0)
                return True
            except Exception:
                self._logger.error(
                    "Progress fallback edit_message_text failed chat_id=%s message_id=%s",
                    message.chat.id,
                    message.message_id,
                    exc_info=True,
                )
                return False
        except Exception:
            self._logger.error(
                "Progress unexpected error chat_id=%s message_id=%s",
                message.chat.id,
                message.message_id,
                exc_info=True,
            )
            return False

    async def run_blocking(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        fn_name = getattr(fn, "__name__", fn.__class__.__name__)
        self._logger.info("Run blocking task in thread fn=%s", fn_name)
        return await asyncio.to_thread(fn, *args, **kwargs)

