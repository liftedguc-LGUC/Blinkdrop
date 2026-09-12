"""Token bucket on the one route an anonymous caller can write through.

Per instance, in memory. Cloud Run autoscales, so an attacker spread across
instances gets a multiple of this limit — the real control is Cloud Armor at the
edge (see README). This makes a single-source flood expensive without adding a
dependency, and it is not a substitute for the edge rule.
"""

import time
from collections import OrderedDict

from fastapi import HTTPException, Request, status

from .config import Settings

_WINDOW_SECONDS = 60.0
_MAX_TRACKED_CLIENTS = 10_000

_hits: OrderedDict[str, list[float]] = OrderedDict()


def _client_key(request: Request) -> str:
    # Cloud Run puts the caller first in X-Forwarded-For; everything after it is
    # proxy hops. Falls back to the socket address for local runs.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, settings: Settings) -> None:
    limit = settings.feedback_rate_limit
    if limit <= 0:
        return

    now = time.monotonic()
    key = _client_key(request)
    recent = [stamp for stamp in _hits.get(key, []) if now - stamp < _WINDOW_SECONDS]

    if len(recent) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many submissions, please try again shortly",
            headers={"Retry-After": str(int(_WINDOW_SECONDS))},
        )

    recent.append(now)
    _hits[key] = recent
    _hits.move_to_end(key)
    # Bounded so the limiter itself cannot be turned into a memory leak by
    # rotating source addresses.
    while len(_hits) > _MAX_TRACKED_CLIENTS:
        _hits.popitem(last=False)


def reset() -> None:
    _hits.clear()
