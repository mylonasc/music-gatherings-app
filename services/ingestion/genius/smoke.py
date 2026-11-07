"""Opt-in live smoke test for the Genius adapter.

Requires GENIUS_ACCESS_TOKEN. Prints metadata only (titles/artists/URLs —
never lyrics) and obeys the same limiter as production traffic.

Usage: python -m genius.smoke "blue train"
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.alimiter import AsyncLimiter  # noqa: E402
from common.client import LimitedHttpClient  # noqa: E402
from common.contracts import SearchRequest  # noqa: E402
from common.limits import LimiterConfig  # noqa: E402
from genius.adapter import GeniusAdapter  # noqa: E402


async def main(query: str) -> int:
    token = os.environ.get("GENIUS_ACCESS_TOKEN")
    if not token:
        print("GENIUS_ACCESS_TOKEN is not set; refusing to run live traffic.")
        return 2
    # Same limiter + client path as production traffic.
    limiter = AsyncLimiter(LimiterConfig())
    adapter = GeniusAdapter(token, client=LimitedHttpClient(limiter))
    response = await adapter.search(SearchRequest(query=query, limit=5))
    if not response.items:
        print(f"no Genius results for {query!r}")
        return 0
    for item in response.items:
        print(f"{item.external_id} | {item.artist} - {item.title} | {item.source_url}")
    print(f"upstream attempts: {adapter.http_client.attempt_count}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m genius.smoke <query>")
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1])))
