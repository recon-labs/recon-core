"""Compiler validation context and diagnostic helpers."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.parser import AuthoredContract

_COMPILER_DIAGNOSTIC_CODE_PREFIXES = ("RC_COMPILE_", "RC_VALIDATE_")


@dataclass(frozen=True, slots=True)
class CompilerDiagnosticContext:
    """Default resource context for compiler-owned diagnostics."""

    resource_type: str | None = None
    resource_name: str | None = None
    path: str | None = None

    def error(
        self,
        *,
        code: str,
        message: str,
        resource_type: str | None = None,
        resource_name: str | None = None,
        path: str | None = None,
        line: int | None = None,
        column: int | None = None,
        hint: str | None = None,
    ) -> Diagnostic:
        return self.diagnostic(
            code=code,
            severity=DiagnosticSeverity.ERROR,
            message=message,
            resource_type=resource_type,
            resource_name=resource_name,
            path=path,
            line=line,
            column=column,
            hint=hint,
        )

    def warning(
        self,
        *,
        code: str,
        message: str,
        resource_type: str | None = None,
        resource_name: str | None = None,
        path: str | None = None,
        line: int | None = None,
        column: int | None = None,
        hint: str | None = None,
    ) -> Diagnostic:
        return self.diagnostic(
            code=code,
            severity=DiagnosticSeverity.WARNING,
            message=message,
            resource_type=resource_type,
            resource_name=resource_name,
            path=path,
            line=line,
            column=column,
            hint=hint,
        )

    def diagnostic(
        self,
        *,
        code: str,
        severity: DiagnosticSeverity,
        message: str,
        resource_type: str | None = None,
        resource_name: str | None = None,
        path: str | None = None,
        line: int | None = None,
        column: int | None = None,
        hint: str | None = None,
    ) -> Diagnostic:
        _validate_compiler_diagnostic_code(code)
        return Diagnostic(
            code=code,
            severity=severity,
            message=message,
            resource_type=self.resource_type if resource_type is None else resource_type,
            resource_name=self.resource_name if resource_name is None else resource_name,
            path=self.path if path is None else path,
            line=line,
            column=column,
            hint=hint,
        )


def contract_diagnostic_context(contract: AuthoredContract) -> CompilerDiagnosticContext:
    """Build compiler diagnostic context from an authored contract."""
    return CompilerDiagnosticContext(
        resource_type="contract",
        resource_name=contract.name,
        path=contract.source_location.path,
    )


def with_default_diagnostic_path(
    diagnostics: Sequence[Diagnostic],
    path: str,
) -> tuple[Diagnostic, ...]:
    """Apply a default path to diagnostics that do not already identify one."""
    return tuple(
        diagnostic if diagnostic.path is not None else replace(diagnostic, path=path)
        for diagnostic in diagnostics
    )


def _validate_compiler_diagnostic_code(code: str) -> None:
    if not code.startswith(_COMPILER_DIAGNOSTIC_CODE_PREFIXES):
        raise ValueError(
            "Compiler diagnostics must use RC_COMPILE_* or RC_VALIDATE_* code families."
        )
