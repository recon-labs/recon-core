"""Diagnostic models for parse, compile, run, and evidence workflows."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict


class DiagnosticSeverity(StrEnum):
    """Severity levels for structured diagnostics."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticDict(TypedDict):
    code: str
    severity: str
    message: str
    resource_type: str | None
    resource_name: str | None
    path: str | None
    line: int | None
    column: int | None
    hint: str | None


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    severity: DiagnosticSeverity
    message: str
    resource_type: str | None = None
    resource_name: str | None = None
    path: str | None = None
    line: int | None = None
    column: int | None = None
    hint: str | None = None

    def to_dict(self) -> DiagnosticDict:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "hint": self.hint,
        }
