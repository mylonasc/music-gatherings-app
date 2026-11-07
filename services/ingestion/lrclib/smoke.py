"""Opt-in live search/fetch; print metadata and sizes, never full lyrics.

Usage: python -m lrclib.smoke "artist song"
"""

import asyncio
import sys

from common.contracts import FetchRequest, SearchRequest
from lrclib.adapter import adapter_from_env


async def main(query: str) -> None:
    adapter = adapter_from_env()
    results = await adapter.search(SearchRequest(query=query, limit=1))
    if not results.items:
        print("No matching records.")
        return
    item = results.items[0]
    print(f"{item.external_id} | {item.artist} - {item.title} | {item.source_url}")
    fetched = await adapter.fetch(FetchRequest(external_id=item.external_id))
    for artifact in fetched.artifacts:
        print(f"{artifact.mime_type}: {len((artifact.content_text or '').encode())} bytes")
    for warning in fetched.warnings:
        print(warning)
    print(f"Upstream attempts: {adapter.http_client.attempt_count}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m lrclib.smoke <query>")
    asyncio.run(main(sys.argv[1]))
