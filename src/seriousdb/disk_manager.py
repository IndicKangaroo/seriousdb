
from __future__ import annotations

import operator
import os
from pathlib import Path
from threading import RLock
from typing import Self, SupportsIndex

from .exceptions import DiskManagerError
from .storage_format import PAGE_SIZE
from .types import UInt32

_O_BINARY = getattr(os, "O_BINARY", 0)  # Windows only; stops newline translation
_HAS_POSITIONAL_IO = hasattr(os, "pread") and hasattr(os, "pwrite")

__all__ = ["DiskManager"]


class DiskManager:
    """Page ``n`` is stored at byte offset ``n * PAGE_SIZE``. This class does raw
page I/O only: it knows nothing about page contents, and locking is left to
the concurrency manager.

    Parameters
    ----------
    path : str or Path
        Path of the database file. It is created if it does not exist.
    repair_torn_page : bool, optional
        If the file ends in a partial page (for example after a crash while
        growing it), truncate it to the last whole page instead of raising.
        Only ever removes the incomplete tail. Defaults to ``False``.

    Raises
    ------
    DiskManagerError
        If the file size is not a multiple of ``PAGE_SIZE`` and
        `repair_torn_page` is false.
    OSError
        If the file cannot be opened.



    A new file has no pages, so the first :meth:`append_page` returns 0.
    The layer that owns the metadata must append and write page 0 first.
    Free-list reuse is also that layer's job; this class only appends.
    """

    def __init__(self, path: str | Path, *, repair_torn_page: bool = False):
        self._path = Path(path)
        self._lock = RLock()
        self._fd: int | None = None
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT | _O_BINARY, 0o644)
        try:
            size = os.fstat(fd).st_size
            tail = size % PAGE_SIZE
            if tail:
                if not repair_torn_page:
                    raise DiskManagerError(
                        f"{self._path} is {size} bytes, not a multiple of "
                        f"{PAGE_SIZE}; the last page is incomplete"
                    )
                os.ftruncate(fd, size - tail)
                os.fsync(fd)
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd

    @property
    def path(self):
        #Path of the database file.
        return self._path

    @property
    def page_count(self) :
        """Number of whole pages currently in the file.

        Read from the file size on every call, so pages appended by another
        process are visible.
        """
        return os.fstat(self._require_open()).st_size // PAGE_SIZE

    def read_page(self, page_id: SupportsIndex):
        """Return the ``PAGE_SIZE`` bytes of page `page_id`.

        Raises
        ------
        DiskManagerError
            If `page_id` is out of range, the file is closed, or the file
            ends before a full page could be read.
        """
        fd = self._require_open()
        offset = self._offset(fd, page_id)
        buf = bytearray()
        while len(buf) < PAGE_SIZE:
            chunk = self._read_at(fd, PAGE_SIZE - len(buf), offset + len(buf))
            if not chunk:
                raise DiskManagerError(f"unexpected end of file reading page {page_id}")
            buf += chunk
        return bytes(buf)

    def write_page(self, page_id: SupportsIndex, data: bytes):
        """Overwrite existing page `page_id` with `data`.
        Raises
        ------
        DiskManagerError
            If `data` is not exactly ``PAGE_SIZE`` bytes, `page_id` has not
            been allocated, or the file is closed.
        """
        fd = self._require_open()
        if len(data) != PAGE_SIZE:
            raise DiskManagerError(
                f"page data must be {PAGE_SIZE} bytes, got {len(data)}"
            )
        self._write_all(fd, data, self._offset(fd, page_id))

    def append_page(self):
        """Grow the file by one zero-filled page and return its ID.

        Not fsynced; call :meth:`sync` before relying on the new size
        after a crash.

        Raises
        ------
        DiskManagerError
            If the file is closed or page IDs would exceed the ``UInt32`` range.
        """
        fd = self._require_open()
        with self._lock:
            count = os.fstat(fd).st_size // PAGE_SIZE
            if count > UInt32.MAX:
                raise DiskManagerError("page ID would exceed the UInt32 range")
            self._write_all(fd, bytes(PAGE_SIZE), count * PAGE_SIZE)
            return UInt32(count)

    def sync(self):
        #Flush file contents and size to stable storage (``fsync``).
        os.fsync(self._require_open())

    def close(self):
        #Close the file. Safe to call more than once.
        with self._lock:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None

    def __enter__(self):
        #Return the manager for use in a ``with`` block.
        return self

    def __exit__(self, *exc_info: object):
        #Close the file when leaving the ``with`` block
        self.close()

    # -- internals ---------------------------------------------------------

    def _require_open(self):
        if self._fd is None:
            raise DiskManagerError("the database file is closed")
        return self._fd

    def _offset(self, fd: int, page_id: SupportsIndex):
        try:
            pid = operator.index(page_id)
        except TypeError as e:
            raise DiskManagerError(f"invalid page ID: {page_id!r}") from e
        count = os.fstat(fd).st_size // PAGE_SIZE
        if not 0 <= pid < count:
            raise DiskManagerError(f"page {pid} is out of range (0..{count - 1})")
        return pid * PAGE_SIZE

    def _read_at(self, fd: int, size: int, offset: int):
        if _HAS_POSITIONAL_IO:
            return os.pread(fd, size, offset)
        with self._lock:  # no pread on Windows: seek + read must be atomic
            os.lseek(fd, offset, os.SEEK_SET)
            return os.read(fd, size)

    def _write_all(self, fd: int, data: bytes, offset: int):
        view = memoryview(data)
        written = 0
        while written < len(view):
            if _HAS_POSITIONAL_IO:
                n = os.pwrite(fd, view[written:], offset + written)
            else:
                with self._lock:
                    os.lseek(fd, offset + written, os.SEEK_SET)
                    n = os.write(fd, view[written:])
            if n <= 0:
                raise DiskManagerError("write made no progress")
            written += n
