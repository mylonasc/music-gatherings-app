"""Object-store interface. Filesystem first, S3-compatible later."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredObject:
    key: str
    sha256: str
    size: int


class ObjectStore(Protocol):
    def put(self, data: bytes) -> StoredObject: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def reconcile(self) -> dict[str, int]: ...
