from __future__ import annotations

import gzip
import json
import logging
import re
import uuid
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import BufferedInputFile, InputSticker

from app.models.pack_result import PackCreationResult
from app.services.pack_service import PackProvider
from app.utils.files import slugify

DEFAULT_LOG_FILE = "bot_debug.log"


class PackCreationError(RuntimeError):
    """Raised when Telegram sticker set creation failed."""


def _ensure_file_and_console_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_emoji_bot_logging_ready", False):
        return

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
    if not has_file:
        file_handler = logging.FileHandler(DEFAULT_LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    if root.level > logging.INFO:
        root.setLevel(logging.INFO)
    setattr(root, "_emoji_bot_logging_ready", True)


class TelegramPackProvider(PackProvider):
    def __init__(
        self,
        bot: Bot,
        sticker_type: str = "custom_emoji",
        sticker_format: str = "animated",
        default_emoji: str = "😀",
    ) -> None:
        _ensure_file_and_console_logging()
        self._bot = bot
        self._sticker_type = sticker_type
        self._sticker_format = sticker_format
        self._default_emoji = default_emoji
        self._logger = logging.getLogger(self.__class__.__name__)
        self._bot_username: str | None = None

    async def _get_bot_username(self) -> str:
        if self._bot_username:
            return self._bot_username
        me = await self._bot.get_me()
        if not me.username:
            raise PackCreationError("Bot username is required for sticker set naming")
        self._bot_username = me.username
        return self._bot_username

    async def _build_set_name(self, title: str) -> str:
        bot_username = (await self._get_bot_username()).lower()
        base_slug = slugify(title, max_len=28)
        if not re.match(r"^[a-z]", base_slug):
            base_slug = f"emoji_{base_slug}"
        suffix = uuid.uuid4().hex[:10]
        candidate = f"{base_slug}_{suffix}_by_{bot_username}"
        candidate = re.sub(r"_+", "_", candidate).strip("_")
        max_len = 64
        if len(candidate) > max_len:
            trim_len = max_len - len(f"_by_{bot_username}")
            candidate = f"{candidate[:trim_len].rstrip('_')}_by_{bot_username}"
        if not candidate.endswith(f"_by_{bot_username}"):
            candidate = f"{candidate}_by_{bot_username}"
        if len(candidate) > max_len:
            candidate = candidate[:max_len]
        return candidate

    def _emoji_list(self, metadata: dict[str, str]) -> list[str]:
        raw = metadata.get("emoji", "").strip()
        if raw:
            items = [token.strip() for token in raw.split() if token.strip()]
            if items:
                return items[:20]
        return [self._default_emoji]

    def _input_sticker(self, filename: str, payload: bytes, emoji_list: list[str]) -> InputSticker:
        input_file = BufferedInputFile(file=payload, filename=filename)
        return InputSticker(
            sticker=input_file,
            format=self._sticker_format,
            emoji_list=emoji_list,
        )

    def _log_payload_debug(
        self,
        *,
        stage: str,
        user_id: int,
        set_name: str,
        filename: str,
        payload: bytes,
    ) -> None:
        first_bytes = payload[:16]
        first_hex = first_bytes.hex()
        ungzipped_len: int | None = None
        root_keys: list[str] | None = None
        layer_count: int | None = None
        layer_ty_values: list[int] | None = None
        error: str | None = None
        try:
            raw_json = gzip.decompress(payload)
            ungzipped_len = len(raw_json)
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                root_keys = sorted(parsed.keys())
                layers = parsed.get("layers")
                if isinstance(layers, list):
                    layer_count = len(layers)
                    type_values = {
                        int(layer.get("ty"))
                        for layer in layers
                        if isinstance(layer, dict) and isinstance(layer.get("ty"), int)
                    }
                    layer_ty_values = sorted(type_values)
        except Exception as exc:
            error = str(exc)

        self._logger.info(
            (
                "Upload payload debug stage=%s user_id=%s set_name=%s filename=%s "
                "size=%s exceeds_64kb=%s first_bytes_hex=%s ungzipped_json_len=%s root_keys=%s layer_count=%s layer_ty=%s parse_error=%s"
            ),
            stage,
            user_id,
            set_name,
            filename,
            len(payload),
            len(payload) > 64 * 1024,
            first_hex,
            ungzipped_len,
            root_keys,
            layer_count,
            layer_ty_values,
            error,
        )

    async def create_pack(
        self,
        user_id: int,
        title: str,
        emoji_files: list[tuple[str, bytes]],
        metadata: dict[str, str],
    ) -> PackCreationResult:
        if not emoji_files:
            raise PackCreationError("No sticker files to create pack")

        set_title = title[:64]
        set_name = await self._build_set_name(set_title)
        emoji_list = self._emoji_list(metadata)
        self._logger.info(
            "Pack create start user_id=%s set_name=%s set_title=%s sticker_type=%s files=%s",
            user_id,
            set_name,
            set_title,
            self._sticker_type,
            len(emoji_files),
        )

        first_filename, first_payload = emoji_files[0]
        self._log_payload_debug(
            stage="create_new_sticker_set",
            user_id=user_id,
            set_name=set_name,
            filename=first_filename,
            payload=first_payload,
        )
        first_sticker = self._input_sticker(first_filename, first_payload, emoji_list)

        try:
            created = await self._bot.create_new_sticker_set(
                user_id=user_id,
                name=set_name,
                title=set_title,
                stickers=[first_sticker],
                sticker_type=self._sticker_type,
                sticker_format=self._sticker_format,
            )
            self._logger.info(
                "createNewStickerSet result user_id=%s set_name=%s success=%s",
                user_id,
                set_name,
                created,
            )
            if not created:
                raise PackCreationError("createNewStickerSet returned False")

            for filename, payload in emoji_files[1:]:
                self._log_payload_debug(
                    stage="add_sticker_to_set",
                    user_id=user_id,
                    set_name=set_name,
                    filename=filename,
                    payload=payload,
                )
                sticker = self._input_sticker(filename, payload, emoji_list)
                added = await self._bot.add_sticker_to_set(
                    user_id=user_id,
                    name=set_name,
                    sticker=sticker,
                )
                self._logger.info(
                    "addStickerToSet result user_id=%s set_name=%s file=%s success=%s",
                    user_id,
                    set_name,
                    filename,
                    added,
                )
                if not added:
                    raise PackCreationError(f"addStickerToSet returned False for {filename}")
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            self._logger.error(
                "Telegram pack creation failed user_id=%s set_name=%s",
                user_id,
                set_name,
                exc_info=True,
            )
            raise PackCreationError(str(exc)) from exc
        except Exception as exc:
            self._logger.error(
                "Unexpected pack creation error user_id=%s set_name=%s",
                user_id,
                set_name,
                exc_info=True,
            )
            raise

        addemoji_link = f"https://t.me/addemoji/{set_name}"
        self._logger.info(
            "Pack create success user_id=%s set_name=%s final_link=%s",
            user_id,
            set_name,
            addemoji_link,
        )
        return PackCreationResult(
            pack_id=set_name,
            pack_title=set_title,
            addemoji_link=addemoji_link,
            public_link=addemoji_link,
            items_count=len(emoji_files),
            metadata=metadata,
        )

