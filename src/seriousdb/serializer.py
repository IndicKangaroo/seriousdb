"""Serialization of SeriousDB storage pages."""

from __future__ import annotations

import struct
from typing import Final

from .storage_format import (
    INTERNAL_PAGE,
    LEAF_PAGE,
    MAGIC,
    PAGE_HEADER_SIZE,
    PAGE_SIZE,
    SLOT_SIZE,
    Node,
    SdbMetadata,
    Slot,
)

# Page header:
#
# page_type          1 byte
# slot_count         2 bytes
# free_start         2 bytes
# free_end           2 bytes
# next_page_id       4 bytes
# leftmost_child_id  4 bytes
# reserved          15 bytes
#
# Total: 32 bytes.
PAGE_HEADER_FORMAT: Final[str] = ">cHHHII15x"

# Slot:
#
# record offset  2 bytes
# record length  2 bytes
SLOT_FORMAT: Final[str] = ">HH"

# Leaf record:
#
# key length    2 bytes
# value length  4 bytes
# key bytes
# value bytes
LEAF_RECORD_HEADER_FORMAT: Final[str] = ">HI"

# Internal record:
#
# key length    2 bytes
# child page ID 4 bytes
# key bytes
INTERNAL_RECORD_HEADER_FORMAT: Final[str] = ">HI"

# Page 0 metadata:
#
# magic
# format version
# page size
# root page ID
# total page count
# free-list head
META_HEADER_FORMAT: Final[str] = ">4sBHIII"


class SerializationError(ValueError):
    """Raised when a page cannot be serialized or deserialized."""


class PageSerializer:
    """Serialize and deserialize SeriousDB pages."""

    @classmethod
    def serialize(cls, node: Node) -> bytes:
        """Serialize a B+ tree node into exactly one page.

        Parameters
        ----------
        node : Node
            Node to serialize.

        Returns
        -------
        bytes
            Exactly ``PAGE_SIZE`` bytes.

        Raises
        ------
        SerializationError
            If the node cannot fit into a single page or contains
            invalid data.
        """
        if node.page_id == 0:
            raise SerializationError("page 0 is reserved for database metadata")

        if node.leaf:
            if len(node.keys) != len(node.values):
                raise SerializationError(
                    "leaf keys and values must have the same length"
                )
        elif len(node.children_ids) != len(node.keys):
            raise SerializationError(
                "internal nodes must have one child ID for each key"
            )

        records: list[bytes] = []

        if node.leaf:
            for key, value in zip(node.keys, node.values):
                records.append(cls._serialize_leaf_record(key, value))
        else:
            for key, child_id in zip(node.keys, node.children_ids):
                records.append(cls._serialize_internal_record(key, child_id))

        slot_count = len(records)
        free_start = PAGE_HEADER_SIZE + slot_count * SLOT_SIZE
        free_end = PAGE_SIZE

        page = bytearray(PAGE_SIZE)
        slots: list[Slot] = []

        # Records grow backwards from the end of the page.
        for record in records:
            free_end -= len(record)

            if free_end < free_start:
                raise SerializationError(
                    f"page {node.page_id} does not have enough space"
                )

            page[free_end : free_end + len(record)] = record

            slots.append(
                Slot(
                    offset=free_end,
                    length=len(record),
                )
            )

        # Slot directory grows forwards after the page header.
        for index, slot in enumerate(slots):
            slot_offset = PAGE_HEADER_SIZE + index * SLOT_SIZE

            struct.pack_into(
                SLOT_FORMAT,
                page,
                slot_offset,
                slot.offset,
                slot.length,
            )

        page_type: bytes = LEAF_PAGE if node.leaf else INTERNAL_PAGE

        header = struct.pack(
            PAGE_HEADER_FORMAT,
            page_type,
            slot_count,
            free_start,
            free_end,
            node.next_page_id if node.leaf else 0,
            node.leftmost_child_id if not node.leaf else 0,
        )

        page[:PAGE_HEADER_SIZE] = header

        return bytes(page)

    @classmethod
    def deserialize(cls, page_id: int, data: bytes) -> Node:
        """Deserialize a B+ tree page.

        Parameters
        ----------
        page_id : int
            ID of the page being deserialized.
        data : bytes
            Raw page data.

        Returns
        -------
        Node
            Deserialized B+ tree node.

        Raises
        ------
        SerializationError
            If the page is invalid or malformed.
        """
        cls._validate_page(data)

        (
            page_type,
            slot_count,
            free_start,
            free_end,
            next_page_id,
            leftmost_child_id,
        ) = struct.unpack(
            PAGE_HEADER_FORMAT,
            data[:PAGE_HEADER_SIZE],
        )

        if page_type not in (LEAF_PAGE, INTERNAL_PAGE):
            raise SerializationError(f"unsupported page type: {page_type!r}")

        cls._validate_header(
            slot_count,
            free_start,
            free_end,
        )

        slots: list[Slot] = cls._read_slots(data, slot_count)

        keys: list[bytes] = []
        if page_type == LEAF_PAGE:
            values: list[bytes] = []

            for slot in slots:
                key, value = cls._deserialize_leaf_record(
                    data,
                    slot,
                )
                keys.append(key)
                values.append(value)

            return Node(
                page_id=page_id,
                leaf=True,
                keys=keys,
                values=values,
                children_ids=[],
                next_page_id=next_page_id,
            )

        children_ids: list[int] = []

        for slot in slots:
            key, child_id = cls._deserialize_internal_record(
                data,
                slot,
            )
            keys.append(key)
            children_ids.append(child_id)

        return Node(
            page_id=page_id,
            leaf=False,
            keys=keys,
            values=[],
            children_ids=children_ids,
            leftmost_child_id=leftmost_child_id,
        )

    @classmethod
    def serialize_metadata(
        cls,
        metadata: SdbMetadata,
    ) -> bytes:
        """Serialize database metadata into page zero.

        Parameters
        ----------
        metadata : DatabaseMetadata
            Database metadata to serialize.

        Returns
        -------
        bytes
            Exactly ``PAGE_SIZE`` bytes.

        Raises
        ------
        SerializationError
            If the metadata is invalid.
        """
        if metadata.format_version < 1:
            raise SerializationError("format version must be positive")

        if metadata.page_size != PAGE_SIZE:
            raise SerializationError(f"unsupported page size: {metadata.page_size}")

        header: bytes = struct.pack(
            META_HEADER_FORMAT,
            MAGIC,
            metadata.format_version,
            metadata.page_size,
            metadata.root_page_id,
            metadata.total_page_count,
            metadata.free_list_head,
        )

        return header + bytes(PAGE_SIZE - len(header))

    @classmethod
    def deserialize_metadata(
        cls,
        data: bytes,
    ) -> SdbMetadata:
        """Deserialize database metadata from page zero.

        Parameters
        ----------
        data : bytes
            Raw metadata page.

        Returns
        -------
        DatabaseMetadata
            Deserialized database metadata.

        Raises
        ------
        SerializationError
            If the metadata page is invalid.
        """
        cls._validate_page(data)

        (
            magic,
            format_version,
            page_size,
            root_page_id,
            total_page_count,
            free_list_head,
        ) = struct.unpack(
            META_HEADER_FORMAT,
            data[: struct.calcsize(META_HEADER_FORMAT)],
        )

        if magic != MAGIC:
            raise SerializationError("invalid SeriousDB magic number")

        if page_size != PAGE_SIZE:
            raise SerializationError(f"unsupported page size: {page_size}")

        if format_version < 1:
            raise SerializationError("unsupported format version")

        return SdbMetadata(
            format_version=format_version,
            page_size=page_size,
            root_page_id=root_page_id,
            total_page_count=total_page_count,
            free_list_head=free_list_head,
        )

    @staticmethod
    def _serialize_leaf_record(
        key: bytes,
        value: bytes,
    ) -> bytes:
        """Serialize a variable-length leaf record."""
        if len(key) > 0xFFFF:
            raise SerializationError("key is too large")

        if len(value) > 0xFFFFFFFF:
            raise SerializationError("value is too large")

        return (
            struct.pack(
                LEAF_RECORD_HEADER_FORMAT,
                len(key),
                len(value),
            )
            + key
            + value
        )

    @staticmethod
    def _serialize_internal_record(
        key: bytes,
        child_id: int,
    ) -> bytes:
        """Serialize a variable-length internal record."""
        if len(key) > 0xFFFF:
            raise SerializationError("key is too large")

        if not 0 <= child_id <= 0xFFFFFFFF:
            raise SerializationError("invalid child page ID")

        return (
            struct.pack(
                INTERNAL_RECORD_HEADER_FORMAT,
                len(key),
                child_id,
            )
            + key
        )

    @staticmethod
    def _deserialize_leaf_record(
        data: bytes,
        slot: Slot,
    ) -> tuple[bytes, bytes]:
        """Deserialize a leaf record."""
        record: bytes = data[slot.offset : slot.offset + slot.length]

        header_size: int = struct.calcsize(LEAF_RECORD_HEADER_FORMAT)

        if len(record) < header_size:
            raise SerializationError("leaf record is truncated")

        key_len, value_len = struct.unpack(
            LEAF_RECORD_HEADER_FORMAT,
            record[:header_size],
        )

        expected_length = header_size + key_len + value_len

        if expected_length != slot.length:
            raise SerializationError("invalid leaf record length")

        key_start: int = header_size
        value_start: int = key_start + key_len

        return (
            bytes(record[key_start:value_start]),
            bytes(record[value_start:]),
        )

    @staticmethod
    def _deserialize_internal_record(
        data: bytes,
        slot: Slot,
    ) -> tuple[bytes, int]:
        """Deserialize an internal record."""
        record = data[slot.offset : slot.offset + slot.length]

        header_size: int = struct.calcsize(INTERNAL_RECORD_HEADER_FORMAT)

        if len(record) < header_size:
            raise SerializationError("internal record is truncated")

        key_len, child_id = struct.unpack(
            INTERNAL_RECORD_HEADER_FORMAT,
            record[:header_size],
        )

        expected_length = header_size + key_len

        if expected_length != slot.length:
            raise SerializationError("invalid internal record length")

        return (
            bytes(record[header_size:]),
            child_id,
        )

    @classmethod
    def _read_slots(
        cls,
        data: bytes,
        slot_count: int,
    ) -> list[Slot]:
        """Read the slot directory from a page."""
        slots: list[Slot] = []

        for index in range(slot_count):
            offset = PAGE_HEADER_SIZE + index * SLOT_SIZE

            record_offset, record_length = struct.unpack(
                SLOT_FORMAT,
                data[offset : offset + SLOT_SIZE],
            )

            if (
                record_offset < PAGE_HEADER_SIZE
                or record_offset + record_length > PAGE_SIZE
            ):
                raise SerializationError("slot points outside the page")

            slots.append(
                Slot(
                    offset=record_offset,
                    length=record_length,
                )
            )

        return slots

    @staticmethod
    def _validate_page(data: bytes) -> None:
        """Validate the size of a raw page."""
        if len(data) != PAGE_SIZE:
            raise SerializationError(
                f"page must be exactly {PAGE_SIZE} bytes, got {len(data)}"
            )

    @staticmethod
    def _validate_header(
        slot_count: int,
        free_start: int,
        free_end: int,
    ) -> None:
        """Validate page header boundaries."""
        expected_free_start = PAGE_HEADER_SIZE + slot_count * SLOT_SIZE

        if free_start != expected_free_start:
            raise SerializationError("invalid free-space start")

        if not (PAGE_HEADER_SIZE <= free_start <= free_end <= PAGE_SIZE):
            raise SerializationError("invalid free-space boundaries")
