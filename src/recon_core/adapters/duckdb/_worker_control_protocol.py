"""Fixed-size private worker control messages; no user data or arbitrary objects."""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import BinaryIO, Final

_MAGIC: Final = b"RCW1"
_LAYOUT: Final = struct.Struct(">4sBQqq")
_MAX_SEQUENCE: Final = (1 << 64) - 1
_MAX_NATIVE_INTEGER: Final = (1 << 63) - 1


class _ControlError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Worker control communication could not be verified.")


class _ControlKind(IntEnum):
    READY = 1
    PROBE = 2
    RECOMMENDATIONS = 3
    CLOSE = 4
    CLOSED = 5
    ERROR = 6


@dataclass(frozen=True, slots=True)
class _ControlPacket:
    kind: _ControlKind
    sequence: int
    first: int = 0
    second: int = 0

    def validate(self) -> None:
        if (
            not isinstance(self.kind, _ControlKind)
            or type(self.sequence) is not int
            or not 0 <= self.sequence <= _MAX_SEQUENCE
            or (self.kind is _ControlKind.READY) != (self.sequence == 0)
            or type(self.first) is not int
            or type(self.second) is not int
        ):
            raise _ControlError()
        if self.kind is _ControlKind.RECOMMENDATIONS:
            if any(
                value != -1 and not 1 <= value <= _MAX_NATIVE_INTEGER
                for value in (self.first, self.second)
            ):
                raise _ControlError()
        elif self.first != 0 or self.second != 0:
            raise _ControlError()


def _read_control(stream: BinaryIO) -> _ControlPacket:
    data = bytearray()
    try:
        while len(data) < _LAYOUT.size:
            chunk = stream.read(_LAYOUT.size - len(data))
            if not chunk or len(chunk) > _LAYOUT.size - len(data):
                raise _ControlError()
            data.extend(chunk)
        magic, kind, sequence, first, second = _LAYOUT.unpack(data)
        if magic != _MAGIC:
            raise _ControlError()
        packet = _ControlPacket(_ControlKind(kind), sequence, first, second)
        packet.validate()
        return packet
    except Exception:
        raise _ControlError() from None


def _write_control(stream: BinaryIO, packet: _ControlPacket) -> None:
    packet.validate()
    try:
        data = _LAYOUT.pack(_MAGIC, packet.kind, packet.sequence, packet.first, packet.second)
        view = memoryview(data)
        while view:
            written = stream.write(view)
            if written is None or not 0 < written <= len(view):
                raise _ControlError()
            view = view[written:]
        stream.flush()
    except Exception:
        raise _ControlError() from None
