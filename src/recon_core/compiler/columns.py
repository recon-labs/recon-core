"""Authored column declaration validation for compiler-owned checks."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from recon_core.compiler.policies import (
    validate_normalization,
    validate_null_policy,
    validate_tolerance,
)
from recon_core.compiler.validation import CompilerDiagnosticContext
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

INVALID_COLUMN_DECLARATION = "RC_VALIDATE_INVALID_COLUMN_DECLARATION"
DUPLICATE_COLUMN_NAME = "RC_VALIDATE_DUPLICATE_COLUMN_NAME"
UNDECLARED_COLUMN_REFERENCE = "RC_VALIDATE_UNDECLARED_COLUMN_REFERENCE"
INVALID_COLUMN_SELECTION = "RC_VALIDATE_INVALID_COLUMN_SELECTION"
INCOMPATIBLE_COLUMN_TYPE = "RC_VALIDATE_INCOMPATIBLE_COLUMN_TYPE"

_COLUMN_CONTEXT = CompilerDiagnosticContext(resource_type="column")
_METRIC_CONTEXT = CompilerDiagnosticContext(resource_type="metric")
_SUPPORTED_COLUMN_CATEGORIES = frozenset({"exact", "numeric", "timestamp", "string"})
_ALLOWED_COLUMN_ENTRY_FIELDS = frozenset(
    {
        "name",
        "description",
        "checks",
        "tolerance",
        "nulls",
        "normalization",
        "timezone",
    }
)


class ColumnCategory(StrEnum):
    """Authored column categories supported by the current compiler."""

    EXACT = "exact"
    NUMERIC = "numeric"
    TIMESTAMP = "timestamp"
    STRING = "string"


@dataclass(frozen=True, slots=True)
class ColumnDeclaration:
    """One typed authored column declaration."""

    name: str
    category: ColumnCategory
    checks: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class ColumnRegistry:
    """Resolved authored column declarations for compiler validation."""

    declarations: tuple[ColumnDeclaration, ...] = ()
    has_explicit_surface: bool = False

    @property
    def names(self) -> frozenset[str]:
        return frozenset(declaration.name for declaration in self.declarations)

    def declaration_for(self, column_name: str) -> ColumnDeclaration:
        for declaration in self.declarations:
            if declaration.name == column_name:
                return declaration
        raise KeyError(column_name)


@dataclass(frozen=True, slots=True)
class ColumnValidationResult:
    """Result of validating authored column declarations."""

    registry: ColumnRegistry
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not any(
            diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in self.diagnostics
        )


def validate_columns(columns: object | None) -> ColumnValidationResult:
    """Validate authored column declarations and build a column registry."""
    if columns is None:
        return ColumnValidationResult(registry=ColumnRegistry())
    if not isinstance(columns, Mapping):
        return ColumnValidationResult(
            registry=ColumnRegistry(has_explicit_surface=True),
            diagnostics=(
                _invalid_column_declaration(
                    "Contract `columns` must be a mapping of column categories."
                ),
            ),
        )

    diagnostics: list[Diagnostic] = []
    declarations: list[ColumnDeclaration] = []
    seen_names: set[str] = set()

    for key, value in columns.items():
        if not isinstance(key, str):
            diagnostics.append(_invalid_column_declaration("Column categories must be strings."))
            continue
        if key == "include":
            diagnostics.extend(_validate_include(value))
            continue
        if key not in _SUPPORTED_COLUMN_CATEGORIES:
            diagnostics.append(_invalid_column_declaration(f"Unknown column category: {key}."))
            continue
        declarations.extend(
            _declarations_for_category(
                category=ColumnCategory(key),
                raw_entries=value,
                seen_names=seen_names,
                diagnostics=diagnostics,
            )
        )

    if diagnostics:
        return ColumnValidationResult(
            registry=ColumnRegistry(has_explicit_surface=True),
            diagnostics=tuple(diagnostics),
        )
    return ColumnValidationResult(
        registry=ColumnRegistry(
            declarations=tuple(declarations),
            has_explicit_surface=True,
        )
    )


def validate_metric_column_references(
    *,
    metric_name: str,
    metric_type: str,
    column: str,
    group_by: Sequence[str],
    column_registry: ColumnRegistry | None,
) -> tuple[Diagnostic, ...]:
    """Validate metric column references against the declared column surface."""
    diagnostics: list[Diagnostic] = []
    referenced_columns = (column, *group_by)
    for referenced_column in referenced_columns:
        if referenced_column == "*":
            diagnostics.append(_invalid_metric_column_selection(metric_name, referenced_column))
    if diagnostics:
        return tuple(diagnostics)

    if column_registry is None or not column_registry.has_explicit_surface:
        return ()

    for referenced_column in referenced_columns:
        if referenced_column not in column_registry.names:
            diagnostics.append(_undeclared_column_reference(metric_name, referenced_column))

    if diagnostics:
        return tuple(diagnostics)

    if metric_type == "sum":
        value_column = column_registry.declaration_for(column)
        if value_column.category is not ColumnCategory.NUMERIC:
            diagnostics.append(
                _incompatible_metric_column_type(
                    metric_name=metric_name,
                    metric_type=metric_type,
                    column_name=value_column.name,
                    category=value_column.category,
                    required_category=ColumnCategory.NUMERIC,
                )
            )

    return tuple(diagnostics)


def _declarations_for_category(
    *,
    category: ColumnCategory,
    raw_entries: object,
    seen_names: set[str],
    diagnostics: list[Diagnostic],
) -> tuple[ColumnDeclaration, ...]:
    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, str):
        diagnostics.append(
            _invalid_column_declaration(
                f"Column category `{category.value}` must be a list of column entries."
            )
        )
        return ()

    declarations: list[ColumnDeclaration] = []
    for raw_entry in raw_entries:
        declaration = _parse_column_entry(category, raw_entry, diagnostics)
        if declaration is None:
            continue
        if declaration.name == "*":
            diagnostics.append(_invalid_column_selection("Wildcard column declarations"))
            continue
        if declaration.name in seen_names:
            diagnostics.append(_duplicate_column_name(declaration.name))
            continue
        seen_names.add(declaration.name)
        declarations.append(declaration)
    return tuple(declarations)


def _parse_column_entry(
    category: ColumnCategory,
    raw_entry: object,
    diagnostics: list[Diagnostic],
) -> ColumnDeclaration | None:
    if isinstance(raw_entry, str):
        if not raw_entry:
            diagnostics.append(_invalid_column_declaration("Column names must be non-empty."))
            return None
        return ColumnDeclaration(name=raw_entry, category=category)

    if not isinstance(raw_entry, Mapping):
        diagnostics.append(
            _invalid_column_declaration("Column entries must be strings or mappings.")
        )
        return None

    if not all(isinstance(key, str) for key in raw_entry):
        diagnostics.append(_invalid_column_declaration("Column entry fields must be strings."))
        return None

    unknown_fields = sorted(set(raw_entry) - _ALLOWED_COLUMN_ENTRY_FIELDS)
    if unknown_fields:
        diagnostics.append(
            _invalid_column_declaration(
                f"Column entry has unsupported fields: {', '.join(unknown_fields)}."
            )
        )
        return None

    name = raw_entry.get("name")
    if not isinstance(name, str) or not name:
        diagnostics.append(_invalid_column_declaration("Column entries require a `name`."))
        return None

    checks = _checks(raw_entry.get("checks"), diagnostics)
    if raw_entry.get("checks") is not None and checks is None:
        return None

    diagnostics.extend(_column_policy_diagnostics(category, name, raw_entry))

    return ColumnDeclaration(name=name, category=category, checks=checks)


def _checks(raw_checks: object, diagnostics: list[Diagnostic]) -> tuple[str, ...] | None:
    if raw_checks is None:
        return None
    if not isinstance(raw_checks, Sequence) or isinstance(raw_checks, str):
        diagnostics.append(_invalid_column_declaration("Column `checks` must be a list."))
        return None
    if not all(isinstance(check, str) and check for check in raw_checks):
        diagnostics.append(
            _invalid_column_declaration("Column `checks` entries must be non-empty strings.")
        )
        return None
    return tuple(raw_checks)


def _validate_include(value: object) -> tuple[Diagnostic, ...]:
    if value == "*":
        return (_invalid_column_selection("Explicit all-column requests"),)
    return (
        _invalid_column_declaration("Column `include` is only supported as `include: \"*\"`."),
    )


def _column_policy_diagnostics(
    category: ColumnCategory,
    column_name: str,
    raw_entry: Mapping[object, object],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []

    if "tolerance" in raw_entry:
        tolerance_result = validate_tolerance(
            raw_entry["tolerance"],
            resource_type="column",
            resource_name=column_name,
        )
        diagnostics.extend(tolerance_result.diagnostics)
        if tolerance_result.succeeded and category is not ColumnCategory.NUMERIC:
            diagnostics.append(
                _incompatible_column_policy(
                    column_name=column_name,
                    policy_name="tolerance",
                    category=category,
                    required_category=ColumnCategory.NUMERIC,
                )
            )

    if "nulls" in raw_entry:
        null_result = validate_null_policy(
            raw_entry["nulls"],
            resource_type="column",
            resource_name=column_name,
        )
        diagnostics.extend(null_result.diagnostics)
        if null_result.succeeded and category is not ColumnCategory.STRING:
            diagnostics.append(
                _incompatible_column_policy(
                    column_name=column_name,
                    policy_name="nulls",
                    category=category,
                    required_category=ColumnCategory.STRING,
                )
            )

    if "normalization" in raw_entry:
        normalization_result = validate_normalization(
            raw_entry["normalization"],
            resource_type="column",
            resource_name=column_name,
        )
        diagnostics.extend(normalization_result.diagnostics)
        if normalization_result.succeeded and category is not ColumnCategory.STRING:
            diagnostics.append(
                _incompatible_column_policy(
                    column_name=column_name,
                    policy_name="normalization",
                    category=category,
                    required_category=ColumnCategory.STRING,
                )
            )

    return tuple(diagnostics)


def _invalid_column_declaration(message: str) -> Diagnostic:
    return _COLUMN_CONTEXT.error(
        code=INVALID_COLUMN_DECLARATION,
        message=message,
        hint="Use supported column categories and string or mapping column entries.",
    )


def _duplicate_column_name(column_name: str) -> Diagnostic:
    return _COLUMN_CONTEXT.error(
        code=DUPLICATE_COLUMN_NAME,
        message=f"Column name {column_name} is declared more than once.",
        resource_name=column_name,
        hint="Declare each canonical column name only once.",
    )


def _invalid_column_selection(selection_description: str) -> Diagnostic:
    return _COLUMN_CONTEXT.error(
        code=INVALID_COLUMN_SELECTION,
        message=(
            f"{selection_description} require adapter metadata and are not supported "
            "in the current compiler milestone."
        ),
        hint="List concrete column names until all-column expansion is implemented.",
    )


def _invalid_metric_column_selection(metric_name: str, column_name: str) -> Diagnostic:
    return _METRIC_CONTEXT.error(
        code=INVALID_COLUMN_SELECTION,
        message=(
            f"Metric {metric_name} references unresolved wildcard column {column_name}."
        ),
        resource_name=metric_name,
        hint="Metric column references must use concrete column names.",
    )


def _undeclared_column_reference(metric_name: str, column_name: str) -> Diagnostic:
    return _METRIC_CONTEXT.error(
        code=UNDECLARED_COLUMN_REFERENCE,
        message=(
            f"Metric {metric_name} references column {column_name}, but it is not "
            "declared in the contract column surface."
        ),
        resource_name=metric_name,
        hint="Declare the column under `columns` or remove the reference.",
    )


def _incompatible_metric_column_type(
    *,
    metric_name: str,
    metric_type: str,
    column_name: str,
    category: ColumnCategory,
    required_category: ColumnCategory,
) -> Diagnostic:
    return _METRIC_CONTEXT.error(
        code=INCOMPATIBLE_COLUMN_TYPE,
        message=(
            f"Metric {metric_name} of type {metric_type} requires a "
            f"{required_category.value} column, but {column_name} is declared as "
            f"{category.value}."
        ),
        resource_name=metric_name,
        hint=(
            f"Move `{column_name}` to `columns.{required_category.value}` "
            "or use a compatible metric."
        ),
    )


def _incompatible_column_policy(
    *,
    column_name: str,
    policy_name: str,
    category: ColumnCategory,
    required_category: ColumnCategory,
) -> Diagnostic:
    return _COLUMN_CONTEXT.error(
        code=INCOMPATIBLE_COLUMN_TYPE,
        message=(
            f"Column policy `{policy_name}` requires a {required_category.value} column, "
            f"but {column_name} is declared as {category.value}."
        ),
        resource_name=column_name,
        hint=f"Move `{column_name}` to `columns.{required_category.value}` or remove the policy.",
    )
