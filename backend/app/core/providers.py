"""Built-in provider registration, shared by configuration and API validation."""

DEFAULT_PROVIDER_URLS = {
    "fake": "http://ingestion-fake:8001",
    "lrclib": "http://ingestion-lrclib:8002",
    "ultimate_guitar": "http://ingestion-ultimate-guitar:8003",
}
PROVIDER_NAMES = tuple(DEFAULT_PROVIDER_URLS)
