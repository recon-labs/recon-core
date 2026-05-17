"""Shared result primitives for command services."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Self, TypedDict

from recon_core.diagnostics import Diagnostic, DiagnosticDict


class ExitCategory(StrEnum):
    SUCCESS = "success"
    CHECK_FAILURE = "check_failure"
    VALIDATION_ERROR = "validation_error"
    RUNTIME_ERROR = "runtime_error"
    CONFIGURATION_ERROR = "configuration_error"


_EXIT_CODES: dict[ExitCategory, int] = {
    ExitCategory.SUCCESS: 0,
    ExitCategory.CHECK_FAILURE: 1,
    ExitCategory.VALIDATION_ERROR: 2,
    ExitCategory.RUNTIME_ERROR: 3,
    ExitCategory.CONFIGURATION_ERROR: 4,
}


def exit_code_for(category: ExitCategory) -> int:
    return _EXIT_CODES[category]


class ServiceResultDict(TypedDict):
    exit_category: str
    exit_code: int
    message: str | None
    diagnostics: list[DiagnosticDict]


@dataclass(frozen=True, slots=True)
class ServiceResult:
    exit_category: ExitCategory
    message: str | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @classmethod
    def success(cls, message: str | None = None) -> Self:
        return cls(exit_category=ExitCategory.SUCCESS, message=message)

    @property
    def succeeded(self) -> bool:
        return self.exit_category is ExitCategory.SUCCESS

    def to_dict(self) -> ServiceResultDict:
        return {
            "exit_category": self.exit_category.value,
            "exit_code": exit_code_for(self.exit_category),
            "message": self.message,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }
