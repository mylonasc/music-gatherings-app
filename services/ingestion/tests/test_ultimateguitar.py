"""Ultimate Guitar adapter tests: honestly disabled, contract-conformant."""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.contracts import FetchRequest, SearchRequest
from common.errors import ProviderError
from ultimateguitar.adapter import UNAVAILABLE_MESSAGE, capabilities, fetch, search
from ultimateguitar.app import app


def test_capabilities_report_disabled() -> None:
    caps = capabilities()
    assert caps.provider == "ultimate_guitar"
    assert caps.supports_search is False
    assert caps.supports_fetch is False
    assert caps.allows_storage is False


def test_search_and_fetch_return_structured_unavailable() -> None:
    async def run() -> None:
        for coro in (search(SearchRequest(query="x")), fetch(FetchRequest(external_id="1"))):
            with pytest.raises(ProviderError) as exc_info:
                await coro
            assert exc_info.value.code == "provider_unavailable"
            assert "licensed API" in exc_info.value.message

    asyncio.run(run())


def test_service_envelope_is_503_with_docs_pointer() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    caps = client.get("/v1/capabilities").json()
    assert caps["supports_search"] is False
    for path, body in (
        ("/v1/search", {"query": "blue"}),
        ("/v1/fetch", {"external_id": "1"}),
    ):
        response = client.post(path, json=body)
        assert response.status_code == 503
        envelope = response.json()
        assert envelope["error"]["code"] == "provider_unavailable"
        assert "PROVIDERS.md" in envelope["error"]["message"]
    assert UNAVAILABLE_MESSAGE  # referenced for documentation reviews
