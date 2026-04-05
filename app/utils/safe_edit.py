from __future__ import annotations

import json
import logging
from hashlib import sha1
from time import perf_counter
from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


def _hash_text(value: str | None) -> str:
    payload = (value or "").encode("utf-8")
    return sha1(payload).hexdigest()


def _hash_markup(markup: InlineKeyboardMarkup | None) -> str:
    if markup is None:
        return "none"
    try:
        payload: Any = markup.model_dump(exclude_none=True)
    except Exception:
        payload = str(markup)
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha1(serialized.encode("utf-8")).hexdigest()


async def safe_edit_message(
    *,
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    logger: logging.Logger | None = None,
    handler_name: str = "",
    callback_data: str | None = None,
    update_id: int | str | None = None,
) -> bool:
    active_logger = logger or logging.getLogger(__name__)
    t0 = perf_counter()
    current_text = message.text or ""
    current_text_hash = _hash_text(current_text)
    next_text_hash = _hash_text(text)
    current_markup_hash = _hash_markup(message.reply_markup)
    next_markup_hash = _hash_markup(reply_markup)

    if current_text_hash == next_text_hash and current_markup_hash == next_markup_hash:
        active_logger.info(
            "Safe edit skip handler_name=%s callback_data=%s update_id=%s duration_ms=%s skipped_not_modified=True",
            handler_name,
            callback_data,
            update_id,
            int((perf_counter() - t0) * 1000),
        )
        return False

    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            active_logger.info(
                "Safe edit benign handler_name=%s callback_data=%s update_id=%s duration_ms=%s skipped_not_modified=True",
                handler_name,
                callback_data,
                update_id,
                int((perf_counter() - t0) * 1000),
            )
            return False
        raise

    active_logger.info(
        "Safe edit success handler_name=%s callback_data=%s update_id=%s duration_ms=%s skipped_not_modified=False",
        handler_name,
        callback_data,
        update_id,
        int((perf_counter() - t0) * 1000),
    )
    return True
