import os
from threading import Barrier, Thread

import pytest

from seriousdb import disk_manager
from seriousdb.disk_manager import DiskManager
from seriousdb.exceptions import DiskManagerError
from seriousdb.storage_format import PAGE_SIZE


@pytest.fixture
def path(tmp_path):
    return tmp_path / "test.sdb"


def page(byte: int) -> bytes:
    return bytes([byte]) * PAGE_SIZE


def test_new_file_is_empty_and_first_append_is_page_zero(path):
    with DiskManager(path) as dm:
        assert dm.page_count == 0
        assert dm.append_page() == 0
        assert dm.append_page() == 1
        assert dm.page_count == 2
        assert path.stat().st_size == 2 * PAGE_SIZE


def test_round_trip_and_reopen(path):
    with DiskManager(path) as dm:
        for i in range(3):
            dm.write_page(dm.append_page(), page(i + 1))
        dm.sync()
    with DiskManager(path) as dm:
        assert dm.page_count == 3
        assert [dm.read_page(i) for i in range(3)] == [page(1), page(2), page(3)]


def test_fresh_page_is_zeroed(path):
    with DiskManager(path) as dm:
        pid = dm.append_page()
        assert dm.read_page(pid) == bytes(PAGE_SIZE)


def test_misaligned_file_rejected(path):
    path.write_bytes(bytes(PAGE_SIZE + 10))
    with pytest.raises(DiskManagerError):
        DiskManager(path)
    assert path.stat().st_size == PAGE_SIZE + 10  # untouched


def test_repair_truncates_only_the_torn_tail(path):
    path.write_bytes(page(7) + page(8) + b"x" * 100)
    with DiskManager(path, repair_torn_page=True) as dm:
        assert dm.page_count == 2
        assert dm.read_page(0) == page(7)
        assert dm.read_page(1) == page(8)
    assert path.stat().st_size == 2 * PAGE_SIZE


@pytest.mark.parametrize("size", [PAGE_SIZE - 1, PAGE_SIZE + 1, 0])
def test_wrong_size_write_rejected(path, size):
    with DiskManager(path) as dm:
        dm.append_page()
        with pytest.raises(DiskManagerError):
            dm.write_page(0, bytes(size))


@pytest.mark.parametrize("bad", [-1, 1, 99, "0", 1.5])
def test_bad_page_id_rejected(path, bad):
    with DiskManager(path) as dm:
        dm.append_page()
        with pytest.raises(DiskManagerError):
            dm.read_page(bad)
        with pytest.raises(DiskManagerError):
            dm.write_page(bad, bytes(PAGE_SIZE))


def test_write_never_grows_file(path):
    with DiskManager(path) as dm:
        with pytest.raises(DiskManagerError):
            dm.write_page(0, bytes(PAGE_SIZE))
        assert dm.page_count == 0


def test_use_after_close_raises(path):
    dm = DiskManager(path)
    dm.close()
    dm.close()  # idempotent
    for call in (dm.append_page, dm.sync, lambda: dm.read_page(0)):
        with pytest.raises(DiskManagerError):
            call()


def test_page_count_sees_other_handles_appends(path):
    with DiskManager(path) as a, DiskManager(path) as b:
        a.append_page()
        assert b.page_count == 1
        assert b.read_page(0) == bytes(PAGE_SIZE)


@pytest.mark.skipif(not hasattr(os, "pread"), reason="needs os.pread")
def test_short_reads_are_retried(path, monkeypatch):
    real = os.pread
    monkeypatch.setattr(
        disk_manager.os, "pread", lambda fd, n, off: real(fd, min(n, 1000), off)
    )
    with DiskManager(path) as dm:
        dm.write_page(dm.append_page(), page(5))
        assert dm.read_page(0) == page(5)


@pytest.mark.skipif(not hasattr(os, "pread"), reason="needs os.pread")
def test_eof_mid_page_raises(path, monkeypatch):
    with DiskManager(path) as dm:
        dm.append_page()
        monkeypatch.setattr(disk_manager.os, "pread", lambda fd, n, off: b"")
        with pytest.raises(DiskManagerError):
            dm.read_page(0)


def test_concurrent_readers_and_writer_never_see_mixed_pages(path):
    n_pages, rounds = 8, 200
    with DiskManager(path) as dm:
        for _ in range(n_pages):
            dm.write_page(dm.append_page(), page(0))
        start = Barrier(5)
        errors: list[str] = []

        def writer():
            start.wait()
            for r in range(rounds):
                for p in range(n_pages):
                    dm.write_page(p, page(r % 250 + 1))

        def reader():
            start.wait()
            for _ in range(rounds):
                for p in range(n_pages):
                    data = dm.read_page(p)
                    if data != data[:1] * PAGE_SIZE:
                        errors.append(f"torn read on page {p}")

        threads = [Thread(target=writer)] + [Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors


def test_concurrent_appends_get_unique_ids(path):
    with DiskManager(path) as dm:
        ids: list[int] = []
        start = Barrier(8)

        def work():
            start.wait()
            ids.extend(int(dm.append_page()) for _ in range(25))

        threads = [Thread(target=work) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sorted(ids) == list(range(200))
        assert dm.page_count == 200
