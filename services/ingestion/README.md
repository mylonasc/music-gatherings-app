# Ingestion services

One adapter per external provider (LRCLIB, disabled Ultimate Guitar, future sources).
Implemented from S07 (contracts, rate limiting, fake provider) and S08
(validated adapters). Private Compose network only; no published ports.

LRCLIB replaces the original Genius service at internal port 8002. It needs no
credentials and supports plain/LRC lyrics for personal local use. See
`PROVIDERS.md` for API/rights limits and the root README for the opt-in live check.
