from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any


def read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fp:
        payload = json.load(fp)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def write_json_file(path: Path, data: dict[str, Any], compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        if compact:
            json.dump(data, fp, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, fp, ensure_ascii=False, indent=2)


def slugify(value: str, max_len: int = 64) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower())
    normalized = normalized.strip("_")
    if not normalized:
        normalized = "pack"
    return normalized[:max_len]


def safe_cleanup_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
