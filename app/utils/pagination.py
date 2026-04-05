from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def page_count(total_items: int, per_page: int) -> int:
    if per_page <= 0:
        return 1
    return max(1, math.ceil(total_items / per_page))


def clamp_page(page: int, total_pages: int) -> int:
    if total_pages <= 1:
        return 1
    return max(1, min(page, total_pages))


def paginate(items: Sequence[T], page: int, per_page: int) -> tuple[list[T], int, int]:
    total_pages = page_count(len(items), per_page)
    current = clamp_page(page, total_pages)
    start = (current - 1) * per_page
    end = start + per_page
    return list(items[start:end]), current, total_pages

