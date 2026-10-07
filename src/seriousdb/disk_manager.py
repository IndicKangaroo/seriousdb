"""Raw fixed-size page I/O on the .sdb database file."""

from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from .exceptions import DiskManagerError
from .storage_format import PAGE_SIZE
from .types import UInt32

__all__ = ["DiskManager"]

# os.pread/os.pwrite do not exist on Windows. Looked up with getattr so that
# type checkers do not depend on the platform they run on.
_pread = getattr(os, "pread", None)
_pwrite = getattr(os, "pwrite", None)
# Windows only: stops newline translation.
_O_BINARY = getattr(os, "O_BINARY", 0)


class DiskManager:
    """Read and write fixed-size pages of the database file by page ID.

    Page n is stored at byte offset n * PAGE_SIZE. This class does raw
    page I/O only: it knows nothing about page contents, and locking is left
    to the concurrency manager.

    Parameters
    ----------
    path : str or Path
        Database file, created if missing.
    repair_torn_page : bool, optional
        Truncate a partial last page instead of raising. Default False.

    Raises
    ------
    DiskManagerError
        If the file size is not a multiple of PAGE_SIZE and
        repair_torn_page is false.
    OSError
        If the file cannot be opened.

    Notes
    -----
    A new file is empty, so the first :meth:allocate_page returns 0 and the
    caller must write the metadata page there.
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
        """Path of the database file."""
        return self._path

    @property
    def page_count(self):
        """Number of whole pages in the file, read from the file size."""
        return os.fstat(self._require_open()).st_size // PAGE_SIZE

<<<<<<< HEAD
    def read_page(self, page_id: UInt32):
        """Return the PAGE_SIZE bytes of page page_id.
=======
    def read_page(self, page_id: UInt32) -> bytes:
        """Return the PAGE_SIZE`` bytes of page page_id.
>>>>>>> 06519f2 (format+generated exception refrence doc)

        Raises
        ------
        DiskManagerError
            If page_id is out of range, the file is closed, or the file
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

<<<<<<< HEAD
    def write_page(self, page_id: UInt32, data: bytes):
=======
    def write_page(self, page_id: UInt32, data: bytes) -> None:
>>>>>>> 06519f2 (format+generated exception refrence doc)
        """Overwrite the existing page page_id with data.

        Not fsynced; call :meth:sync when the write must be durable.

        Raises
        ------
        DiskManagerError
            If data is not exactly PAGE_SIZE bytes, page_id has not
            been allocated, or the file is closed.
        """
        fd = self._require_open()
        if len(data) != PAGE_SIZE:
            raise DiskManagerError(
                f"page data must be {PAGE_SIZE} bytes, got {len(data)}"
            )
        self._write_all(fd, data, self._offset(fd, page_id))

    def allocate_page(self):
        """Allocate a new page at the end of the file and return its ID.

        The page is zero-filled. Reusing freed pages is the caller's job.
        Not fsynced; call :meth:sync before relying on the new size after
        a crash.

        Raises
        ------
        DiskManagerError
            If the file is closed or page IDs would exceed the UInt32 range.
        """
        fd = self._require_open()
        with self._lock:
            count = os.fstat(fd).st_size // PAGE_SIZE
            if count > UInt32.MAX:
                raise DiskManagerError("page ID would exceed the UInt32 range")
            self._write_all(fd, bytes(PAGE_SIZE), count * PAGE_SIZE)
            return UInt32(count)

    def sync(self):
        """Flush file contents and size to stable storage (fsync)."""
        os.fsync(self._require_open())

    def close(self):
        """Close the file. Safe to call more than once."""
        with self._lock:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None

    def __enter__(self):
        """Return the manager for use in a ``with`` block."""
        return self

<<<<<<< HEAD
    def __exit__(self, *exc_info: object):
=======
    def __exit__(self, *exc_info: object) -> None:
>>>>>>> 06519f2 (format+generated exception refrence doc)
        """Close the file when leaving the ``with`` block."""
        self.close()

    def _require_open(self):
        if self._fd is None:
            raise DiskManagerError("the database file is closed")
        return self._fd

<<<<<<< HEAD
    def _offset(self, fd: int, page_id: UInt32):
=======
    def _offset(self, fd: int, page_id: UInt32) -> int:
>>>>>>> 06519f2 (format+generated exception refrence doc)
        count = os.fstat(fd).st_size // PAGE_SIZE
        if not 0 <= page_id < count:
            raise DiskManagerError(f"page {page_id} is out of range (0..{count - 1})")
        return page_id * PAGE_SIZE

    def _read_at(self, fd: int, size: int, offset: int):
        if _pread is not None:
            return _pread(fd, size, offset)
        with self._lock:  # seek + read must be atomic without pread
            os.lseek(fd, offset, os.SEEK_SET)
            return os.read(fd, size)

    def _write_all(self, fd: int, data: bytes, offset: int):
        view = memoryview(data)
        written = 0
        while written < len(view):
            if _pwrite is not None:
                n = _pwrite(fd, view[written:], offset + written)
            else:
                with self._lock:
                    os.lseek(fd, offset + written, os.SEEK_SET)
                    n = os.write(fd, view[written:])
            if n <= 0:
                raise DiskManagerError("write made no progress")
            written += n
