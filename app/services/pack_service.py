from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod

from app.models.pack_result import PackCreationResult
from app.utils.files import slugify


class PackProvider(ABC):
    @abstractmethod
    async def create_pack(
        self,
        user_id: int,
        title: str,
        emoji_files: list[tuple[str, bytes]],
        metadata: dict[str, str],
    ) -> PackCreationResult:
        raise NotImplementedError


class FakePackProvider(PackProvider):
    async def create_pack(
        self,
        user_id: int,
        title: str,
        emoji_files: list[tuple[str, bytes]],
        metadata: dict[str, str],
    ) -> PackCreationResult:
        pack_uuid = uuid.uuid4().hex[:10]
        safe_title = slugify(title, max_len=32)
        pack_slug = f"test_pack_{safe_title}_{pack_uuid}"
        addemoji_link = f"https://t.me/addemoji/{pack_slug}"
        public_link = addemoji_link
        return PackCreationResult(
            pack_id=pack_slug,
            pack_title=title,
            addemoji_link=addemoji_link,
            public_link=public_link,
            items_count=len(emoji_files),
            metadata=metadata,
        )


class EmojiPackService:
    def __init__(self, provider: PackProvider) -> None:
        self._provider = provider
        self._logger = logging.getLogger(self.__class__.__name__)

    async def create_pack(
        self,
        user_id: int,
        title: str,
        emoji_files: list[tuple[str, bytes]],
        metadata: dict[str, str],
    ) -> PackCreationResult:
        self._logger.info(
            "PackService create start user_id=%s title=%s files=%s provider=%s",
            user_id,
            title,
            len(emoji_files),
            self._provider.__class__.__name__,
        )
        result = await self._provider.create_pack(user_id, title, emoji_files, metadata)
        self._logger.info(
            "PackService create success user_id=%s pack_id=%s addemoji_link=%s",
            user_id,
            result.pack_id,
            result.addemoji_link,
        )
        return result
