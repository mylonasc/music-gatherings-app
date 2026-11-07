"""Local filesystem object store with opaque keys and atomic writes.

Layout under ``root``::

    objects/<shard>/<opaque-id>   immutable stored bytes
    staging/<opaque-id>.part       in-progress writes

Keys are server-generated (``<shard>/<hex>``) and validated on every access,
so client input can never escape the store directory. Writes go to a temp file
in the same directory followed by ``os.replace`` for atomicity.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
import uuid
from pathlib import Path

from app.storage.base import StoredObject

_KEY_RE = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{32}$")
_STAGING_RE = re.compile(r"^[0-9a-f]{32}\.part$")

DEFAULT_STALE_STAGING_SECONDS = 24 * 3600


class ObjectStoreError(ValueError):
    pass


class ObjectTooLargeError(ObjectStoreError):
    pass


class LocalObjectStore:
    def __init__(
        self,
        root: str | Path,
        *,
        max_bytes: int = 50 * 1024 * 1024,
        stale_staging_seconds: int = DEFAULT_STALE_STAGING_SECONDS,
    ) -> None:
        self._root = Path(root)
        self._objects = self._root / "objects"
        self._staging = self._root / "staging"
        self._max_bytes = max_bytes
        self._stale_staging_seconds = stale_staging_seconds

    def ensure_dirs(self) -> None:
        """Create store directories. Called by operations and the entrypoint."""
        self._objects.mkdir(parents=True, exist_ok=True)
        self._staging.mkdir(parents=True, exist_ok=True)

    # -- writes ---------------------------------------------------------

    def put(self, data: bytes) -> StoredObject:
        if len(data) > self._max_bytes:
            raise ObjectTooLargeError(
                f"object of {len(data)} bytes exceeds limit of {self._max_bytes}"
            )
        self.ensure_dirs()
        key = self._fresh_key()
        shard_dir = self._objects / key.split("/")[0]
        shard_dir.mkdir(parents=True, exist_ok=True)
        target = self._objects / key
        tmp_path = shard_dir / f".{uuid.uuid4().hex}.tmp"
        with open(tmp_path, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
        digest = hashlib.sha256(data).hexdigest()
        return StoredObject(key=key, sha256=digest, size=len(data))

    # -- reads ----------------------------------------------------------

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            raise ObjectStoreError("unknown object key") from None

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except ObjectStoreError:
            return False

    # -- deletion -------------------------------------------------------

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        try:
            path.unlink()
        except FileNotFoundError:
            raise ObjectStoreError("unknown object key") from None

    # -- maintenance ----------------------------------------------------

    def reconcile(self) -> dict[str, int]:
        """Remove stale staging fragments. Returns counts of work done."""
        if not self._staging.is_dir():
            return {"removed_staging": 0}
        now = time.time()
        removed_staging = 0
        for entry in self._staging.iterdir():
            if not _STAGING_RE.fullmatch(entry.name):
                continue
            age = now - entry.stat().st_mtime
            if age >= self._stale_staging_seconds:
                entry.unlink(missing_ok=True)
                removed_staging += 1
        return {"removed_staging": removed_staging}

    def write_staging_fragment(self, name: str, data: bytes) -> Path:
        """Test/maintenance helper: simulate an interrupted staging write."""
        if not _STAGING_RE.fullmatch(name):
            raise ObjectStoreError("invalid staging name")
        self.ensure_dirs()
        path = self._staging / name
        path.write_bytes(data)
        return path

    # -- internals ------------------------------------------------------

    def _fresh_key(self) -> str:
        raw = uuid.uuid4().hex
        return f"{raw[:2]}/{raw}"

    def _resolve(self, key: str) -> Path:
        if not _KEY_RE.fullmatch(key):
            raise ObjectStoreError("invalid object key")
        return self._objects / key
