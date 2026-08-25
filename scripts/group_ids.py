"""Parse one or many VK group IDs from environment."""

from __future__ import annotations

import os
import re


def parse_group_ids(
    group_id: str | None = None,
    group_ids: str | None = None,
) -> list[int]:
    """Return unique group IDs, preserving order.

    Reads VK_GROUP_IDS then VK_GROUP_ID when arguments are omitted.
    Accepts commas, spaces, or semicolons. Strips a leading minus.
    """
    if group_ids is None:
        group_ids = os.environ.get("VK_GROUP_IDS", "")
    if group_id is None:
        group_id = os.environ.get("VK_GROUP_ID", "")

    chunks: list[str] = []
    for raw in (group_ids, group_id):
        text = (raw or "").strip()
        if not text:
            continue
        chunks.extend(re.split(r"[\s,;]+", text))

    result: list[int] = []
    seen: set[int] = set()
    for chunk in chunks:
        if not chunk:
            continue
        value = chunk.strip().lstrip("-")
        if not value.isdigit():
            raise ValueError(f"invalid group id: {chunk}")
        gid = int(value)
        if gid <= 0:
            raise ValueError(f"invalid group id: {chunk}")
        if gid not in seen:
            seen.add(gid)
            result.append(gid)

    if not result:
        raise ValueError("set VK_GROUP_IDS and/or VK_GROUP_ID")
    return result
