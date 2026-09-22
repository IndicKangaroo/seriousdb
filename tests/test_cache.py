import json
from pathlib import Path

import pytest
from pytest import MonkeyPatch

from seriousdb.cache import Cache
from seriousdb.exceptions import ServiceUnavailableError


def boom(*args, **kwargs):
    raise RuntimeError("simulated crash mid-flush")


def test_flush_failure_does_not_corrupt_existing_file(
    tmp_path: Path, monkeypatch: MonkeyPatch
):
    db_file = tmp_path / ".sdb"
    cache = Cache()
    cache.load(str(db_file))
    cache.insert("name", "Alice")
    cache.flush()
    original_content = db_file.read_bytes()

    cache.insert("name", "Bob")

    monkeypatch.setattr(json, "dumps", boom)

    with pytest.raises(RuntimeError):
        cache.flush()

    assert db_file.read_bytes() == original_content


def test_load_corrupt_backup_collision_preserves_backups(
    tmp_path: Path, monkeypatch: MonkeyPatch
):
    db_file = tmp_path / "database.sdb"
    first_payload = b"FIRST_CORRUPT_PAYLOAD"
    second_payload = b"SECOND_CORRUPT_PAYLOAD"

    # 1. Create a temporary database file and write FIRST_CORRUPT_PAYLOAD
    db_file.write_bytes(first_payload)

    # 2. Freeze/mock the timestamp used for backup naming
    fixed_timestamp = 1700000000.0
    monkeypatch.setattr("seriousdb.cache.time.time", lambda: fixed_timestamp)

    # 3. Trigger normal corruption recovery
    cache = Cache()
    cache.load(str(db_file))

    # 4. Write SECOND_CORRUPT_PAYLOAD to the same database path
    db_file.write_bytes(second_payload)

    # 5. Trigger recovery again with the same timestamp
    cache.load(str(db_file))

    # 6. Assert that two distinct backup files exist and neither was overwritten
    backup_1 = tmp_path / f"database.sdb.corrupt-{int(fixed_timestamp)}"
    backup_2 = tmp_path / f"database.sdb.corrupt-{int(fixed_timestamp)}-1"

    assert backup_1.exists(), f"Expected {backup_1} to exist"
    assert backup_2.exists(), f"Expected {backup_2} to exist"

    assert backup_1.read_bytes() == first_payload
    assert backup_2.read_bytes() == second_payload

    # 7. Assert that the active database is valid after recovery
    assert cache.db == {}
    assert json.loads(db_file.read_bytes()) == {}
    cache.insert("test_key", "test_val")
    cache.flush()
    assert json.loads(db_file.read_bytes()) == {"test_key": "test_val"}


def test_load_corrupt_backup_with_existing_collision_suffixes(
    tmp_path: Path, monkeypatch: MonkeyPatch
):
    db_file = tmp_path / "database.sdb"
    fixed_timestamp = 1700000000.0
    monkeypatch.setattr("seriousdb.cache.time.time", lambda: fixed_timestamp)

    # Pre-create multiple collision suffixes:
    # .corrupt-1700000000, .corrupt-1700000000-1, .corrupt-1700000000-2
    existing_backups = [
        tmp_path / f"database.sdb.corrupt-{int(fixed_timestamp)}",
        tmp_path / f"database.sdb.corrupt-{int(fixed_timestamp)}-1",
        tmp_path / f"database.sdb.corrupt-{int(fixed_timestamp)}-2",
    ]
    for i, backup in enumerate(existing_backups):
        backup.write_bytes(f"EXISTING_PAYLOAD_{i}".encode())

    # Write corrupt payload and trigger recovery with the same timestamp
    third_payload = b"THIRD_CORRUPT_PAYLOAD"
    db_file.write_bytes(third_payload)

    cache = Cache()
    cache.load(str(db_file))

    # Verify implementation chooses another unused path safely (-3)
    new_backup = tmp_path / f"database.sdb.corrupt-{int(fixed_timestamp)}-3"
    assert new_backup.exists(), f"Expected {new_backup} to exist"
    assert new_backup.read_bytes() == third_payload

    # Verify all existing backups were preserved
    for i, backup in enumerate(existing_backups):
        assert backup.read_bytes() == f"EXISTING_PAYLOAD_{i}".encode()

    assert cache.db == {}
    assert json.loads(db_file.read_bytes()) == {}


def test_cache_unloaded_operations_raise_service_unavailable():
    cache = Cache()

    with pytest.raises(ServiceUnavailableError):
        cache.exists("key")

    with pytest.raises(ServiceUnavailableError):
        _ = "key" in cache

    with pytest.raises(ServiceUnavailableError):
        cache.count()

    with pytest.raises(ServiceUnavailableError):
        _ = len(cache)

    with pytest.raises(ServiceUnavailableError):
        cache.get_all()

    with pytest.raises(ServiceUnavailableError):
        cache.get_bulk(["key"])


def test_cache_exists_and_contains(tmp_path: Path):
    db_file = tmp_path / ".sdb"
    cache = Cache()
    cache.load(str(db_file))

    assert not cache.exists("name")
    assert "name" not in cache

    cache.insert("name", "Alice")

    assert cache.exists("name")
    assert "name" in cache


def test_cache_count_and_len(tmp_path: Path):
    db_file = tmp_path / ".sdb"
    cache = Cache()
    cache.load(str(db_file))

    assert cache.count() == 0
    assert len(cache) == 0

    cache.insert("a", "1")
    cache.insert("b", "2")

    assert cache.count() == 2
    assert len(cache) == 2

    cache.delete("a")

    assert cache.count() == 1
    assert len(cache) == 1


def test_cache_get_all_returns_snapshot_copy(tmp_path: Path):
    db_file = tmp_path / ".sdb"
    cache = Cache()
    cache.load(str(db_file))
    cache.insert("k1", "v1")
    cache.insert("k2", "v2")

    snapshot = cache.get_all()
    assert snapshot == {"k1": "v1", "k2": "v2"}

    # Mutating snapshot should not affect cache
    snapshot["k1"] = "mutated"
    assert cache.select("k1") == "v1"


def test_cache_get_bulk_with_iterable(tmp_path: Path):
    db_file = tmp_path / ".sdb"
    cache = Cache()
    cache.load(str(db_file))
    cache.insert("k1", "v1")
    cache.insert("k2", "v2")

    # Works with list
    assert cache.get_bulk(["k1", "k3"]) == {"k1": "v1"}

    # Works with generator
    def key_gen():
        yield "k2"
        yield "missing"

    assert cache.get_bulk(key_gen()) == {"k2": "v2"}
