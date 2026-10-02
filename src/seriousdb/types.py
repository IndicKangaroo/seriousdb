"""SeriousDB's own custom types."""

from typing import Self, SupportsIndex
import operator


class UInt(int):
    """Base class for unsigned integers type."""

    MAX: int = 0xFFFFFFFFFFFFFFFF

    def __new__(cls, value: SupportsIndex) -> Self:
        """Create an unsigned integer after validating its range."""
        # changed from value = int(value) beause int silently truncate floating points
        value = operator.index(value)

        if value < 0:
            raise ValueError("unsigned integers cannot be negative")

        if value > cls.MAX:
            raise ValueError(f"integer overflow. maximum for {cls.__name__}: {cls.MAX}")

        return super().__new__(cls, value)


class UInt8(UInt):
    """Unsigned 8-bit integer."""

    MAX: int = 0xFF


class UInt16(UInt):
    """Unsigned 16-bit integer."""

    MAX: int = 0xFFFF


class UInt32(UInt):
    """Unsigned 32-bit integer."""

    MAX: int = 0xFFFFFFFF


class UInt64(UInt):
    """Unsigned 64-bit integer."""
