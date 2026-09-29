"""Definitions for the SeriousDB on-disk storage format."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# -----------------------------------
# Database format
# -----------------------------------

PAGE_SIZE: Final[int] = 4096
PAGE_HEADER_SIZE: Final[int] = 32
SLOT_SIZE: Final[int] = 4

FORAMT_VERSION: Final[int] = 1
MAGIC: Final[bytes] = b"SDB\x00"


# -----------------------------------
# Page types
# -----------------------------------

LEAF_PAGE: Final[bytes] = b"L"
INTERNAL_PAGE: Final[bytes] = b"I"
META_PAGE: Final[bytes] = b"M"


# -----------------------------------
# Page header
# -----------------------------------
#
# Common page header:
#
#  page_type         1   byte
#  slot_count        2   bytes
#  free_start        2   bytes
#  free_end          2   bytes
#  next_page_id      4   bytes
#  leftmost_child_id  4   bytes
#  reserved          15  bytes
#
#  Toatl:            32  bytes.
#
# The reseerved bytes are intentionally left unused for now. They can
# eventually hold things such as an LSN or checksum without changing the page
# size or moving the rest of the page layout.

PAGE_HEADER_RESERVED_SIZE: Final[int] = 15


# -----------------------------------
# Page 0 metadata
# -----------------------------------


@dataclass(slots=True)
class SdbMetadata:
    """Metadata stored in page zero."""

    format_version: int
    page_size: int
    root_page_id: int
    total_page_count: int
    free_list_head: int


# -----------------------------------
# B+ tree page representation
# -----------------------------------


@dataclass(slots=True)
class Node:
    """In-memory representaion of a B+ tree page."""

    page_id: int
    leaf: bool
    keys: list[bytes]
    values: list[bytes]
    children_ids: list[int]
    next_page_id: int = 0
    leftmost_child_id: int = 0


@dataclass(slots=True)
class Slot:
    """Location of a record inside a page."""

    offset: int
    length: int
