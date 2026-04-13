from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import Document, InputStickerSetShortName

PACK_LINK_RE = re.compile(
    r"(?:https?://)?t\.me/(?:addemoji|addstickers)/(?P<short>[A-Za-z0-9_]+)",
    flags=re.IGNORECASE,
)
GZIP_MAGIC = b"\x1f\x8b"


@dataclass
class RunConfig:
    api_id: int
    api_hash: str
    pack_short_name: str
    bot_username: str
    out_dir: Path
    session_name: str
    delay_sec: float
    reply_timeout: float
    max_reply_messages: int
    limit: int | None
    start_with: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Send all stickers/emojis from a pack to a target bot one by one, "
            "download bot replies, and unpack .tgs to .json."
        )
    )
    parser.add_argument(
        "--pack",
        required=True,
        help="Sticker pack link or short name. Example: https://t.me/addemoji/pack_name",
    )
    parser.add_argument(
        "--bot",
        required=True,
        help="Target bot username. Example: @StickerDowloadBot",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output directory. Example: passport",
    )
    parser.add_argument(
        "--session",
        default="tg_user_session",
        help="Telethon session filename (without extension). Default: tg_user_session",
    )
    parser.add_argument(
        "--api-id",
        type=int,
        default=None,
        help="Telegram API ID (fallback: TELEGRAM_API_ID env var)",
    )
    parser.add_argument(
        "--api-hash",
        default=None,
        help="Telegram API hash (fallback: TELEGRAM_API_HASH env var)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.2,
        help="Delay between sends in seconds. Default: 1.2",
    )
    parser.add_argument(
        "--reply-timeout",
        type=float,
        default=30.0,
        help="Timeout for one bot reply in seconds. Default: 30",
    )
    parser.add_argument(
        "--max-reply-messages",
        type=int,
        default=5,
        help="How many bot messages to inspect per sent sticker. Default: 5",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of stickers to process",
    )
    parser.add_argument(
        "--start-with",
        default="/start",
        help="Optional message sent to bot before processing. Use '' to disable. Default: /start",
    )
    return parser.parse_args()


def normalize_pack_short_name(raw: str) -> str:
    value = raw.strip()
    match = PACK_LINK_RE.search(value)
    if match:
        return match.group("short")
    if re.fullmatch(r"[A-Za-z0-9_]+", value):
        return value
    raise ValueError("Could not parse pack short name. Provide addemoji/addstickers link or short name.")


def normalize_bot_username(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("Bot username is empty.")
    if value.startswith("https://t.me/") or value.startswith("http://t.me/"):
        value = value.rsplit("/", 1)[-1]
    if not value.startswith("@"):
        value = f"@{value}"
    return value


def build_config(args: argparse.Namespace) -> RunConfig:
    api_id_raw = args.api_id if args.api_id is not None else os.getenv("TELEGRAM_API_ID")
    api_hash = args.api_hash or os.getenv("TELEGRAM_API_HASH")

    if api_id_raw is None:
        raise ValueError("Missing api_id. Pass --api-id or set TELEGRAM_API_ID.")
    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise ValueError("api_id must be an integer.") from exc
    if not api_hash:
        raise ValueError("Missing api_hash. Pass --api-hash or set TELEGRAM_API_HASH.")

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    return RunConfig(
        api_id=api_id,
        api_hash=api_hash,
        pack_short_name=normalize_pack_short_name(args.pack),
        bot_username=normalize_bot_username(args.bot),
        out_dir=out_dir,
        session_name=args.session,
        delay_sec=max(0.0, args.delay),
        reply_timeout=max(1.0, args.reply_timeout),
        max_reply_messages=max(1, args.max_reply_messages),
        limit=args.limit if (args.limit is None or args.limit > 0) else None,
        start_with=(args.start_with or "").strip() or None,
    )


def build_pack_emoji_map(sticker_set: Any) -> dict[int, str]:
    emoji_by_doc_id: dict[int, str] = {}
    for pack in getattr(sticker_set, "packs", []):
        emoji = getattr(pack, "emoticon", "") or ""
        for doc_id in getattr(pack, "documents", []):
            if isinstance(doc_id, int):
                emoji_by_doc_id[doc_id] = emoji
    return emoji_by_doc_id


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w\-.]+", "_", value.strip(), flags=re.UNICODE).strip("._")
    return cleaned or "file"


def unpack_tgs_to_json(source_path: Path, target_path: Path) -> None:
    raw_bytes = source_path.read_bytes()
    unzipped = gzip.decompress(raw_bytes)
    text = unzipped.decode("utf-8")
    parsed = json.loads(text)
    target_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")


def maybe_unpack_gzip_json(source_path: Path, target_path: Path) -> bool:
    raw_bytes = source_path.read_bytes()
    if not raw_bytes.startswith(GZIP_MAGIC):
        return False
    try:
        unzipped = gzip.decompress(raw_bytes)
        text = unzipped.decode("utf-8")
        parsed = json.loads(text)
    except Exception:
        return False
    target_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def extension_from_document(document: Document, default_ext: str = ".bin") -> str:
    ext = default_ext
    mime_type = (getattr(document, "mime_type", "") or "").lower()
    if "tgsticker" in mime_type:
        return ".tgs"
    if "json" in mime_type:
        return ".json"
    if "zip" in mime_type:
        return ".zip"
    if "gzip" in mime_type:
        return ".gz"
    return ext


async def get_reply_with_document(conv: Any, max_messages: int) -> Any | None:
    for _ in range(max_messages):
        message = await conv.get_response()
        if getattr(message, "document", None):
            return message
    return None


async def process_all(config: RunConfig) -> None:
    raw_dir = config.out_dir / "downloads"
    json_dir = config.out_dir / "json"
    raw_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(config.session_name, config.api_id, config.api_hash)
    await client.start()

    print(f"[1/5] Logged in. Loading pack: {config.pack_short_name}")
    sticker_set = await client(
        GetStickerSetRequest(
            stickerset=InputStickerSetShortName(short_name=config.pack_short_name),
            hash=0,
        )
    )
    docs: list[Document] = list(getattr(sticker_set, "documents", []))
    if config.limit is not None:
        docs = docs[: config.limit]
    if not docs:
        print("No stickers found in pack.")
        await client.disconnect()
        return

    emoji_by_doc_id = build_pack_emoji_map(sticker_set)
    print(f"[2/5] Stickers to process: {len(docs)}")
    print(f"[3/5] Opening conversation with {config.bot_username}")

    manifest: list[dict[str, Any]] = []
    success_count = 0

    async with client.conversation(config.bot_username, timeout=config.reply_timeout) as conv:
        if config.start_with:
            await conv.send_message(config.start_with)
            try:
                await get_reply_with_document(conv, max_messages=1)
            except Exception:
                pass

        for index, document in enumerate(docs, start=1):
            doc_id = int(getattr(document, "id"))
            emoji = emoji_by_doc_id.get(doc_id, "")
            row: dict[str, Any] = {
                "index": index,
                "source_doc_id": doc_id,
                "source_emoji": emoji,
                "status": "pending",
            }
            manifest.append(row)

            base_name = sanitize_filename(f"{index:04d}_{doc_id}")
            print(f"  -> [{index}/{len(docs)}] sending {base_name}")

            try:
                await conv.send_file(document)
                reply_message = await get_reply_with_document(conv, config.max_reply_messages)
                if reply_message is None:
                    row["status"] = "no_document_reply"
                    continue

                reply_doc: Document = reply_message.document
                ext = extension_from_document(reply_doc, default_ext=".bin")
                raw_path = raw_dir / f"{base_name}{ext}"
                downloaded_path = await client.download_media(reply_message, file=str(raw_path))
                if not downloaded_path:
                    row["status"] = "download_failed"
                    continue

                final_raw_path = Path(downloaded_path).resolve()
                row["downloaded_file"] = str(final_raw_path)
                row["status"] = "downloaded"

                json_path = json_dir / f"{base_name}.json"
                unpacked = False
                if final_raw_path.suffix.lower() == ".tgs":
                    unpack_tgs_to_json(final_raw_path, json_path)
                    unpacked = True
                else:
                    unpacked = maybe_unpack_gzip_json(final_raw_path, json_path)

                if unpacked:
                    row["json_file"] = str(json_path.resolve())
                    row["status"] = "ok"
                    success_count += 1
                else:
                    row["status"] = "downloaded_non_tgs"
            except FloodWaitError as exc:
                wait_sec = int(getattr(exc, "seconds", 0)) + 1
                row["status"] = "flood_wait"
                row["error"] = f"Flood wait: sleep {wait_sec}s"
                print(f"     flood wait {wait_sec}s")
                await asyncio.sleep(wait_sec)
            except (RPCError, OSError, json.JSONDecodeError, gzip.BadGzipFile, UnicodeDecodeError) as exc:
                row["status"] = "error"
                row["error"] = str(exc)
            except Exception as exc:
                row["status"] = "error"
                row["error"] = f"{exc.__class__.__name__}: {exc}"

            if config.delay_sec > 0:
                await asyncio.sleep(config.delay_sec)

    manifest_path = config.out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "pack_short_name": config.pack_short_name,
                "bot_username": config.bot_username,
                "total_requested": len(docs),
                "ok_count": success_count,
                "items": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("[4/5] Done.")
    print(f"Saved downloads: {raw_dir}")
    print(f"Saved json:      {json_dir}")
    print(f"Saved manifest:  {manifest_path}")
    print(f"[5/5] Success count: {success_count}/{len(docs)}")

    await client.disconnect()


def main() -> int:
    if load_dotenv is not None:
        load_dotenv()

    try:
        args = parse_args()
        config = build_config(args)
    except ValueError as exc:
        print(f"Argument error: {exc}")
        return 2

    try:
        asyncio.run(process_all(config))
    except KeyboardInterrupt:
        print("Interrupted by user.")
        return 130
    except Exception as exc:
        print(f"Failed: {exc.__class__.__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
