"""Compiled checks artifact loader for the first run boundary."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

import yaml

from recon_core.artifacts._paths import reject_symlinked_path_components
from recon_core.artifacts.compiled_check_writer import COMPILED_CHECKS_DIR_NAME
from recon_core.compiler.models import (
    _OPERATION_ALLOWED_FIELDS,
    COMPILED_ARTIFACT_VERSION,
    IdentityKind,
    KeyDiffDirection,
    OperationSide,
    OperationType,
    RenderingStatus,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

COMPILED_CHECK_ARTIFACT_NOT_FOUND = "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND"
COMPILED_CHECK_ARTIFACT_INVALID = "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID"
NO_COMPILED_CHECKS = "RC_RUNTIME_NO_COMPILED_CHECKS"
_OPERATION_BASE_FIELDS: Final[frozenset[str]] = frozenset({"type"})
_RESERVED_OPERATION_METADATA_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "execution_placement",
        "comparison_location",
        "materialization_policy",
    }
)


class _UniqueKeySafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    """YAML safe loader that rejects duplicate mapping keys."""


@dataclass(frozen=True, slots=True)
class LoadedCheckPlan:
    """Loaded typed plan metadata preserved from a compiled check artifact."""

    id: str
    operations: tuple[dict[str, object], ...]
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LoadedCompiledCheck:
    """Loaded compiled check metadata used by the runtime boundary."""

    id: str
    name: str
    check_type: str
    contract_name: str
    plan: LoadedCheckPlan
    rendering_status: str | None = None
    prerequisites: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    payload: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class LoadedCompiledChecksArtifact:
    """Loaded compiled checks artifact for one contract."""

    path: Path
    project_name: str
    project_version: str | None
    contract_id: str
    contract_name: str
    source_file: str
    checks: tuple[LoadedCompiledCheck, ...]
    diagnostics: tuple[Diagnostic, ...] = ()
    payload: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class CompiledCheckLoadResult:
    """Result for loading compiled check artifacts."""

    artifacts: tuple[LoadedCompiledChecksArtifact, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not self.diagnostics


class _ArtifactShapeError(ValueError):
    """Internal shape validation error."""


class CompiledCheckLoader:
    """Load compiled checks artifacts from a target directory."""

    def load(self, target_path: Path) -> CompiledCheckLoadResult:
        compiled_checks_dir = target_path / COMPILED_CHECKS_DIR_NAME
        path_diagnostic = _symlinked_artifact_path_diagnostic(compiled_checks_dir)
        if path_diagnostic is not None:
            return CompiledCheckLoadResult(diagnostics=(path_diagnostic,))
        if not compiled_checks_dir.exists():
            return CompiledCheckLoadResult(
                diagnostics=(_missing_artifacts_diagnostic(compiled_checks_dir),)
            )
        if not compiled_checks_dir.is_dir() or compiled_checks_dir.is_symlink():
            return CompiledCheckLoadResult(
                diagnostics=(
                    _invalid_artifact_diagnostic(
                        compiled_checks_dir,
                        "Compiled-check artifact path is not a real directory.",
                    ),
                )
            )

        artifact_paths = tuple(sorted(compiled_checks_dir.glob("*.yml")))
        if not artifact_paths:
            return CompiledCheckLoadResult(
                diagnostics=(_no_compiled_checks_diagnostic(compiled_checks_dir),)
            )

        artifacts: list[LoadedCompiledChecksArtifact] = []
        diagnostics: list[Diagnostic] = []
        seen_check_ids: set[str] = set()

        for artifact_path in artifact_paths:
            artifact, artifact_diagnostics = self._load_artifact(
                artifact_path,
                seen_check_ids=seen_check_ids,
            )
            diagnostics.extend(artifact_diagnostics)
            if artifact is not None:
                artifacts.append(artifact)

        if diagnostics:
            return CompiledCheckLoadResult(diagnostics=tuple(diagnostics))
        if not any(artifact.checks for artifact in artifacts):
            empty_scope_path = artifacts[0].path if len(artifacts) == 1 else compiled_checks_dir
            return CompiledCheckLoadResult(
                diagnostics=(_no_compiled_checks_diagnostic(empty_scope_path),)
            )

        return CompiledCheckLoadResult(
            artifacts=tuple(artifacts),
        )

    def _load_artifact(
        self,
        artifact_path: Path,
        *,
        seen_check_ids: set[str],
    ) -> tuple[LoadedCompiledChecksArtifact | None, tuple[Diagnostic, ...]]:
        path_diagnostic = _symlinked_artifact_path_diagnostic(artifact_path)
        if path_diagnostic is not None:
            return None, (path_diagnostic,)
        try:
            payload = _read_yaml_mapping(artifact_path)
            artifact = _parse_artifact(
                artifact_path,
                payload,
                seen_check_ids=seen_check_ids,
            )
        except yaml.YAMLError:
            return None, (
                _invalid_artifact_diagnostic(
                    artifact_path,
                    "Compiled-check artifact is invalid YAML.",
                ),
            )
        except (OSError, UnicodeDecodeError):
            return None, (
                _invalid_artifact_diagnostic(
                    artifact_path,
                    "Compiled-check artifact could not be read.",
                ),
            )
        except _ArtifactShapeError as error:
            return None, (_invalid_artifact_diagnostic(artifact_path, str(error)),)

        return artifact, ()


def _read_yaml_mapping(path: Path) -> dict[str, object]:
    loaded: object = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader)
    return dict(_as_mapping(loaded, "artifact root"))


def _construct_mapping_without_duplicate_keys(
    loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}

    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            hash(key)
        except TypeError as error:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"Unsupported YAML mapping key: {key}",
                key_node.start_mark,
            ) from error

        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"Duplicate YAML key: {key}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)

    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicate_keys,
)


def _symlinked_artifact_path_diagnostic(path: Path) -> Diagnostic | None:
    try:
        reject_symlinked_path_components(path)
    except FileExistsError:
        return _invalid_artifact_diagnostic(
            path,
            "Compiled-check artifact path contains a symlink.",
        )
    return None


def _parse_artifact(
    path: Path,
    payload: dict[str, object],
    *,
    seen_check_ids: set[str],
) -> LoadedCompiledChecksArtifact:
    artifact_type = _required_string(payload, "artifact_type", "artifact_type")
    if artifact_type != "compiled_checks":
        raise _ArtifactShapeError(
            "Compiled-check artifact field artifact_type must be compiled_checks."
        )

    artifact_version = _required_int(payload, "artifact_version", "artifact_version")
    if artifact_version != COMPILED_ARTIFACT_VERSION:
        raise _ArtifactShapeError(
            "Compiled-check artifact field artifact_version is not supported."
        )

    project = _required_mapping(payload, "project", "project")
    project_name = _required_string(project, "name", "project.name")
    project_version = _optional_string(project, "version", "project.version")

    contract = _required_mapping(payload, "contract", "contract")
    contract_id = _required_string(contract, "id", "contract.id")
    contract_name = _required_string(contract, "name", "contract.name")
    source_file = _required_string(contract, "source_file", "contract.source_file")

    raw_checks = _required_list(payload, "checks", "checks")
    checks = tuple(
        _parse_check(
            check_payload,
            contract_name=contract_name,
            index=index,
            seen_check_ids=seen_check_ids,
        )
        for index, check_payload in enumerate(raw_checks)
    )

    diagnostics = _parse_diagnostics(payload.get("diagnostics"), "diagnostics")

    return LoadedCompiledChecksArtifact(
        path=path,
        project_name=project_name,
        project_version=project_version,
        contract_id=contract_id,
        contract_name=contract_name,
        source_file=source_file,
        checks=checks,
        diagnostics=diagnostics,
        payload=payload,
    )


def _parse_check(
    value: object,
    *,
    contract_name: str,
    index: int,
    seen_check_ids: set[str],
) -> LoadedCompiledCheck:
    path = f"checks[{index}]"
    check = _as_mapping(value, path)
    check_id = _required_string(check, "id", f"{path}.id")
    if check_id in seen_check_ids:
        raise _ArtifactShapeError(
            f"Compiled-check artifact contains duplicate check id: {check_id}."
        )
    seen_check_ids.add(check_id)

    name = _required_string(check, "name", f"{path}.name")
    check_type = _required_string(check, "type", f"{path}.type")
    _required_identity(check, "identity", f"{path}.identity", require_keys=False)
    plan = _parse_plan(_required_mapping(check, "plan", f"{path}.plan"), path=f"{path}.plan")
    prerequisites = _optional_string_tuple(check, "prerequisites", f"{path}.prerequisites")
    diagnostics = _parse_diagnostics(check.get("diagnostics"), f"{path}.diagnostics")
    rendering_status = _parse_rendering_status(check, path=path, diagnostics=diagnostics)

    return LoadedCompiledCheck(
        id=check_id,
        name=name,
        check_type=check_type,
        contract_name=contract_name,
        plan=plan,
        rendering_status=rendering_status,
        prerequisites=prerequisites,
        diagnostics=diagnostics,
        payload=dict(check),
    )


def _parse_rendering_status(
    check: Mapping[str, object],
    *,
    path: str,
    diagnostics: tuple[Diagnostic, ...],
) -> str | None:
    if "rendering" not in check or check["rendering"] is None:
        return None

    rendering = _as_mapping(check["rendering"], f"{path}.rendering")
    status = _required_string(rendering, "status", f"{path}.rendering.status")
    if status in {RenderingStatus.BLOCKED.value, RenderingStatus.FAILED.value} and not any(
        diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in diagnostics
    ):
        raise _ArtifactShapeError(
            f"Compiled-check artifact field {path}.rendering.status is {status}, "
            f"but {path}.diagnostics has no error diagnostic."
        )
    return status


def _parse_plan(plan: Mapping[str, object], *, path: str) -> LoadedCheckPlan:
    plan_id = _required_string(plan, "id", f"{path}.id")
    raw_operations = _required_list(plan, "operations", f"{path}.operations")
    if not raw_operations:
        raise _ArtifactShapeError(
            f"Compiled-check artifact field {path}.operations must not be empty."
        )
    operations = tuple(
        _parse_operation(operation, path=f"{path}.operations[{index}]")
        for index, operation in enumerate(raw_operations)
    )
    required_capabilities = _required_string_tuple(
        plan,
        "required_capabilities",
        f"{path}.required_capabilities",
    )
    return LoadedCheckPlan(
        id=plan_id,
        operations=operations,
        required_capabilities=required_capabilities,
    )


def _parse_operation(value: object, *, path: str) -> dict[str, object]:
    operation = _as_mapping(value, path)
    operation_type = _required_string(operation, "type", f"{path}.type")
    _validate_known_operation_shape(operation, operation_type=operation_type, path=path)
    return dict(operation)


def _validate_known_operation_shape(
    operation: Mapping[str, object],
    *,
    operation_type: str,
    path: str,
) -> None:
    try:
        typed_operation = OperationType(operation_type)
    except ValueError:
        return

    _reject_unexpected_known_operation_fields(operation, typed_operation, path=path)

    if typed_operation in {
        OperationType.ROW_COUNT,
        OperationType.NULL_KEY,
        OperationType.DUPLICATE_KEY,
        OperationType.AGGREGATE,
        OperationType.GROUPED_AGGREGATE,
    }:
        _required_enum_value(
            operation,
            "side",
            f"{path}.side",
            allowed_values={side.value for side in OperationSide},
        )

    if typed_operation is OperationType.KEY_DIFF:
        _required_enum_value(
            operation,
            "direction",
            f"{path}.direction",
            allowed_values={direction.value for direction in KeyDiffDirection},
        )

    if typed_operation in {
        OperationType.KEY_DIFF,
        OperationType.NULL_KEY,
        OperationType.DUPLICATE_KEY,
    }:
        _required_identity(operation, "identity", f"{path}.identity")

    if typed_operation in {OperationType.AGGREGATE, OperationType.GROUPED_AGGREGATE}:
        _required_string(operation, "aggregate", f"{path}.aggregate")
        _required_string(operation, "column", f"{path}.column")

    if typed_operation is OperationType.GROUPED_AGGREGATE:
        group_by = _required_string_tuple(operation, "group_by", f"{path}.group_by")
        if not group_by:
            raise _ArtifactShapeError(
                f"Compiled-check artifact field {path}.group_by must not be empty."
            )


def _reject_unexpected_known_operation_fields(
    operation: Mapping[str, object],
    typed_operation: OperationType,
    *,
    path: str,
) -> None:
    allowed_payload_fields = _OPERATION_ALLOWED_FIELDS.get(typed_operation, frozenset())
    allowed_fields = (
        _OPERATION_BASE_FIELDS | allowed_payload_fields | _RESERVED_OPERATION_METADATA_FIELDS
    )
    unexpected_fields = sorted(set(operation) - allowed_fields)
    if unexpected_fields:
        raise _ArtifactShapeError(
            f"Compiled-check artifact field {path}: {typed_operation.value} "
            f"operation does not allow: {', '.join(unexpected_fields)}."
        )


def _parse_diagnostics(value: object, path: str) -> tuple[Diagnostic, ...]:
    if value is None:
        return ()
    raw_diagnostics = _as_list(value, path)
    return tuple(
        _parse_diagnostic(diagnostic, path=f"{path}[{index}]")
        for index, diagnostic in enumerate(raw_diagnostics)
    )


def _parse_diagnostic(value: object, *, path: str) -> Diagnostic:
    diagnostic = _as_mapping(value, path)
    severity_value = _required_string(diagnostic, "severity", f"{path}.severity")
    try:
        severity = DiagnosticSeverity(severity_value)
    except ValueError as error:
        raise _ArtifactShapeError(
            f"Compiled-check artifact field {path}.severity is invalid."
        ) from error

    return Diagnostic(
        code=_required_string(diagnostic, "code", f"{path}.code"),
        severity=severity,
        message=_required_string(diagnostic, "message", f"{path}.message"),
        resource_type=_optional_string(diagnostic, "resource_type", f"{path}.resource_type"),
        resource_name=_optional_string(diagnostic, "resource_name", f"{path}.resource_name"),
        path=_optional_string(diagnostic, "path", f"{path}.path"),
        line=_optional_int(diagnostic, "line", f"{path}.line"),
        column=_optional_int(diagnostic, "column", f"{path}.column"),
        hint=_optional_string(diagnostic, "hint", f"{path}.hint"),
    )


def _required_mapping(
    mapping: Mapping[str, object],
    key: str,
    path: str,
) -> Mapping[str, object]:
    if key not in mapping:
        raise _ArtifactShapeError(f"Compiled-check artifact is missing field {path}.")
    return _as_mapping(mapping[key], path)


def _required_string(mapping: Mapping[str, object], key: str, path: str) -> str:
    if key not in mapping:
        raise _ArtifactShapeError(f"Compiled-check artifact is missing field {path}.")
    value = mapping[key]
    if not isinstance(value, str) or not value:
        raise _ArtifactShapeError(f"Compiled-check artifact field {path} must be a string.")
    return value


def _required_enum_value(
    mapping: Mapping[str, object],
    key: str,
    path: str,
    *,
    allowed_values: set[str],
) -> str:
    value = _required_string(mapping, key, path)
    if value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise _ArtifactShapeError(
            f"Compiled-check artifact field {path} must be one of: {allowed}."
        )
    return value


def _required_identity(
    mapping: Mapping[str, object],
    key: str,
    path: str,
    *,
    require_keys: bool = True,
) -> None:
    identity = _required_mapping(mapping, key, path)
    _required_enum_value(
        identity,
        "kind",
        f"{path}.kind",
        allowed_values={identity_kind.value for identity_kind in IdentityKind},
    )
    keys = _required_string_tuple(identity, "keys", f"{path}.keys")
    if require_keys and not keys:
        raise _ArtifactShapeError(f"Compiled-check artifact field {path}.keys must not be empty.")


def _optional_string(mapping: Mapping[str, object], key: str, path: str) -> str | None:
    if key not in mapping or mapping[key] is None:
        return None
    value = mapping[key]
    if not isinstance(value, str) or not value:
        raise _ArtifactShapeError(f"Compiled-check artifact field {path} must be a string.")
    return value


def _required_int(mapping: Mapping[str, object], key: str, path: str) -> int:
    if key not in mapping:
        raise _ArtifactShapeError(f"Compiled-check artifact is missing field {path}.")
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise _ArtifactShapeError(f"Compiled-check artifact field {path} must be an integer.")
    return value


def _optional_int(mapping: Mapping[str, object], key: str, path: str) -> int | None:
    if key not in mapping or mapping[key] is None:
        return None
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise _ArtifactShapeError(f"Compiled-check artifact field {path} must be an integer.")
    return value


def _required_list(mapping: Mapping[str, object], key: str, path: str) -> list[object]:
    if key not in mapping:
        raise _ArtifactShapeError(f"Compiled-check artifact is missing field {path}.")
    return _as_list(mapping[key], path)


def _required_string_tuple(
    mapping: Mapping[str, object],
    key: str,
    path: str,
) -> tuple[str, ...]:
    values = _required_list(mapping, key, path)
    return _string_tuple(values, path)


def _optional_string_tuple(
    mapping: Mapping[str, object],
    key: str,
    path: str,
) -> tuple[str, ...]:
    if key not in mapping or mapping[key] is None:
        return ()
    return _string_tuple(_as_list(mapping[key], path), path)


def _string_tuple(values: list[object], path: str) -> tuple[str, ...]:
    strings: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value:
            raise _ArtifactShapeError(
                f"Compiled-check artifact field {path}[{index}] must be a string."
            )
        strings.append(value)
    return tuple(strings)


def _as_mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise _ArtifactShapeError(f"Compiled-check artifact field {path} must be a mapping.")
    if any(not isinstance(key, str) for key in value):
        raise _ArtifactShapeError(f"Compiled-check artifact field {path} must use string keys.")
    return cast(Mapping[str, object], value)


def _as_list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise _ArtifactShapeError(f"Compiled-check artifact field {path} must be a list.")
    return cast(list[object], value)


def _missing_artifacts_diagnostic(path: Path) -> Diagnostic:
    return Diagnostic(
        code=COMPILED_CHECK_ARTIFACT_NOT_FOUND,
        severity=DiagnosticSeverity.ERROR,
        message="Expected compiled-check artifacts are missing.",
        resource_type="compiled_check_artifact",
        path=str(path),
        hint="Run `recon compile` before `recon run`.",
    )


def _invalid_artifact_diagnostic(path: Path, message: str) -> Diagnostic:
    return Diagnostic(
        code=COMPILED_CHECK_ARTIFACT_INVALID,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="compiled_check_artifact",
        path=str(path),
        hint="Regenerate compiled check artifacts with `recon compile`.",
    )


def _no_compiled_checks_diagnostic(path: Path) -> Diagnostic:
    return Diagnostic(
        code=NO_COMPILED_CHECKS,
        severity=DiagnosticSeverity.ERROR,
        message="No compiled checks are available in the requested run scope.",
        resource_type="compiled_check_artifact",
        path=str(path),
        hint="Run `recon compile` and confirm at least one check compiles.",
    )
