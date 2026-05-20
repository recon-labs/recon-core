"""Shared parser models."""

from dataclasses import dataclass
from typing import TypedDict


class SourceLocationDict(TypedDict):
    path: str
    line: int | None
    column: int | None


@dataclass(frozen=True, slots=True)
class SourceLocation:
    """Best-effort location of an authored resource in source files."""

    path: str
    line: int | None = None
    column: int | None = None

    def to_dict(self) -> SourceLocationDict:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
        }
