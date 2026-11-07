"""Local object store: immutability, traversal safety, recovery, restore."""

import hashlib
import shutil
import uuid

import pytest

from app.storage.local import LocalObjectStore, ObjectStoreError, ObjectTooLargeError


@pytest.fixture()
def store(tmp_path):  # type: ignore[no-untyped-def]
    return LocalObjectStore(tmp_path / "store")


def test_put_get_roundtrip_with_hash(store):  # type: ignore[no-untyped-def]
    data = b"lyrics bytes"
    stored = store.put(data)
    assert stored.size == len(data)
    assert stored.sha256 == hashlib.sha256(data).hexdigest()
    assert store.get(stored.key) == data
    assert store.exists(stored.key)


def test_objects_are_immutable_and_opaque(store):  # type: ignore[no-untyped-def]
    first = store.put(b"same bytes")
    second = store.put(b"same bytes")
    assert first.key != second.key
    assert first.sha256 == second.sha256


def test_path_traversal_rejected(store):  # type: ignore[no-untyped-def]
    for bad_key in (
        "../secret",
        "../../etc/passwd",
        "/absolute/path",
        "ab",
        "ab/",
        "zz/not-hex-at-all-0000000000000000",
        "ab/cd",
        "ab/" + "cd" * 16 + "/extra",
        "",
    ):
        with pytest.raises(ObjectStoreError):
            store.get(bad_key)
        with pytest.raises(ObjectStoreError):
            store.delete(bad_key)
        assert not store.exists(bad_key)


def test_unknown_key_raises_without_leaking(store):  # type: ignore[no-untyped-def]
    missing = f"ab/{uuid.uuid4().hex}"
    with pytest.raises(ObjectStoreError):
        store.get(missing)
    with pytest.raises(ObjectStoreError):
        store.delete(missing)


def test_size_bound_enforced(tmp_path):  # type: ignore[no-untyped-def]
    store = LocalObjectStore(tmp_path / "tiny", max_bytes=4)
    with pytest.raises(ObjectTooLargeError):
        store.put(b"too long")
    assert store.put(b"ok!").size == 3


def test_reconcile_removes_only_stale_staging(tmp_path):  # type: ignore[no-untyped-def]
    store = LocalObjectStore(tmp_path / "s", stale_staging_seconds=3600)
    stale = store.write_staging_fragment("a" * 32 + ".part", b"interrupted")
    fresh = store.write_staging_fragment("b" * 32 + ".part", b"fresh")
    old_mtime = fresh.stat().st_mtime - 7200
    import os

    os.utime(stale, (old_mtime, old_mtime))
    report = store.reconcile()
    assert report == {"removed_staging": 1}
    assert not stale.exists()
    assert fresh.exists()


def test_backup_restore_roundtrip(tmp_path, store):  # type: ignore[no-untyped-def]
    stored = store.put(b"precious tabs")
    backup = tmp_path / "backup"
    shutil.copytree(tmp_path / "store", backup)
    store.delete(stored.key)
    assert not store.exists(stored.key)
    shutil.rmtree(tmp_path / "store")
    shutil.copytree(backup, tmp_path / "store")
    assert store.get(stored.key) == b"precious tabs"
