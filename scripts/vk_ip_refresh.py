"""One extra OAuth refresh after groups.getRequests IP retries fail.

Retry 5/1130 with the same token lives in VkClient.get_requests.
This helper adds at most one force refresh per process, then re-runs
all group_ids with the new token (not only IP-failed). Never loop refresh.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from scripts.vk_client import IP_RETRY_CODES, VkApiError, VkClient

T = TypeVar("T")


class OneExtraRefresh:
    """force=True refresh at most once per process."""

    def __init__(self) -> None:
        self.done = False

    def maybe_apply(self, client: VkClient) -> bool:
        if self.done:
            return False
        from scripts.vk_oauth import refresh_from_env

        print(
            "WARN getRequests still error 5/1130 after retries; "
            "one extra refresh then retry all groups with the new token (not a loop)"
        )
        tokens = refresh_from_env(force=True)
        client.access_token = str(tokens["access_token"]).strip()
        self.done = True
        return True


def ip_probe_failed(result: dict[str, Any]) -> bool:
    return (not result.get("ok")) and result.get("error_code") in IP_RETRY_CODES


def run_per_group_with_one_extra_refresh(
    client: VkClient,
    group_ids: Sequence[int],
    fn: Callable[[VkClient, int], T],
    *,
    ip_from_result: Callable[[T], bool] | None = None,
) -> tuple[VkClient, dict[int, T | VkApiError]]:
    """Call fn for each group; on IP failure, one extra refresh then retry all groups."""
    extra = OneExtraRefresh()
    original = [int(gid) for gid in group_ids]
    remaining = list(original)
    latest: dict[int, T | VkApiError] = {}
    while remaining:
        still_ip: list[int] = []
        for gid in remaining:
            try:
                result = fn(client, gid)
            except VkApiError as exc:
                latest[gid] = exc
                if exc.code in IP_RETRY_CODES:
                    still_ip.append(gid)
                continue
            latest[gid] = result
            if ip_from_result and ip_from_result(result):
                still_ip.append(gid)
        if still_ip and extra.maybe_apply(client):
            remaining = list(original)
            continue
        break
    return client, latest


def call_recovering_ip(client: VkClient, extra: OneExtraRefresh, fn: Callable[[], T]) -> T:
    """Run fn; if it raises IP error, one extra refresh then retry once."""
    try:
        return fn()
    except VkApiError as exc:
        if exc.code in IP_RETRY_CODES and extra.maybe_apply(client):
            return fn()
        raise
