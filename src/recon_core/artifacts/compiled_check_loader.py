"""Compiled checks artifact loader for the first run boundary."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from recon_core.artifacts.compiled_check_writer import COMPILED_CHECKS_DIR_NAME
from recon_core.compiler.models import COMPILED_ARTIFACT_VERSION
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

COMPILED_CHECK_ARTIFACT_NOT_FOUND = "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_NOT_FOUND"
COMPILED_CHECK_ARTIFACT_INVALID = "RC_RUNTIME_COMPILED_CHECK_ARTIFACT_INVALID"
NO_COMPILED_CHECKS = "RC_RUNTIME_NO_COMPILED_CHECKS"


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


class _NoCompiledChecksError(ValueError):
    """Internal empty compiled-check scope marker."""


class CompiledCheckLoader:
    """Load compiled checks artifacts from a target directory."""

    def load(self, target_path: Path) -> CompiledCheckLoadResult:
        compiled_checks_dir = target_path / COMPILED_CHECKS_DIR_NAME
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

        return CompiledCheckLoadResult(
            artifacts=tuple(artifacts) if not diagnostics else (),
            diagnostics=tuple(diagnostics),
        )

    def _load_artifact(
        self,
        artifact_path: Path,
        *,
        seen_check_ids: set[str],
    ) -> tuple[LoadedCompiledChecksArtifact | None, tuple[Diagnostic, ...]]:
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
        except _NoCompiledChecksError:
            return None, (_no_compiled_checks_diagnostic(artifact_path),)
        except _ArtifactShapeError as error:
            return None, (_invalid_artifact_diagnostic(artifact_path, str(error)),)

        return artifact, ()


def _read_yaml_mapping(path: Path) -> dict[str, object]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise _ArtifactShapeError("Compiled-check artifact root must be a mapping.")
    return cast(dict[str, object], loaded)


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
    if not raw_checks:
        raise _NoCompiledChecksError

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
    plan = _parse_plan(_required_mapping(check, "plan", f"{path}.plan"), path=f"{path}.plan")
    prerequisites = _optional_string_tuple(check, "prerequisites", f"{path}.prerequisites")
    diagnostics = _parse_diagnostics(check.get("diagnostics"), f"{path}.diagnostics")

    return LoadedCompiledCheck(
        id=check_id,
        name=name,
        check_type=check_type,
        contract_name=contract_name,
        plan=plan,
        prerequisites=prerequisites,
        diagnostics=diagnostics,
        payload=dict(check),
    )


def _parse_plan(plan: Mapping[str, object], *, path: str) -> LoadedCheckPlan:
    plan_id = _required_string(plan, "id", f"{path}.id")
    raw_operations = _required_list(plan, "operations", f"{path}.operations")
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
    _required_string(operation, "type", f"{path}.type")
    return dict(operation)


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
    if not isinstance(value, int):
        raise _ArtifactShapeError(f"Compiled-check artifact field {path} must be an integer.")
    return value


def _optional_int(mapping: Mapping[str, object], key: str, path: str) -> int | None:
    if key not in mapping or mapping[key] is None:
        return None
    value = mapping[key]
    if not isinstance(value, int):
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
