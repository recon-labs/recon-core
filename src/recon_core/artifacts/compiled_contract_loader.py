"""Compiled contract artifact loader for runtime execution."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from recon_core._yaml import load_yaml_with_unique_keys
from recon_core.artifacts._paths import reject_symlinked_path_components
from recon_core.artifacts.compiled_check_loader import LoadedCompiledChecksArtifact
from recon_core.artifacts.compiled_contract_writer import COMPILED_CONTRACTS_DIR_NAME
from recon_core.compiler.models import COMPILED_ARTIFACT_VERSION
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

COMPILED_CONTRACT_ARTIFACT_NOT_FOUND = "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_NOT_FOUND"
COMPILED_CONTRACT_ARTIFACT_INVALID = "RC_RUNTIME_COMPILED_CONTRACT_ARTIFACT_INVALID"


@dataclass(frozen=True, slots=True)
class LoadedCompiledEndpoint:
    """Loaded source or target endpoint metadata from a compiled contract."""

    connection: str
    relation: str | None = None
    query: str | None = None


@dataclass(frozen=True, slots=True)
class LoadedCompiledContractArtifact:
    """Loaded compiled contract metadata needed by runtime execution."""

    path: Path
    project_name: str
    project_version: str | None
    contract_id: str
    contract_name: str
    source_file: str
    source: LoadedCompiledEndpoint
    target: LoadedCompiledEndpoint
    grain_keys: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class CompiledContractLoadResult:
    """Result for loading compiled contract artifacts."""

    artifacts: tuple[LoadedCompiledContractArtifact, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not self.diagnostics


class _ArtifactShapeError(ValueError):
    """Internal shape validation error."""


class CompiledContractLoader:
    """Load compiled contract artifacts from a target directory."""

    def load(self, target_path: Path) -> CompiledContractLoadResult:
        compiled_contracts_dir = target_path / COMPILED_CONTRACTS_DIR_NAME
        directory_diagnostic = _compiled_contracts_directory_diagnostic(compiled_contracts_dir)
        if directory_diagnostic is not None:
            return CompiledContractLoadResult(diagnostics=(directory_diagnostic,))

        artifact_paths = tuple(sorted(compiled_contracts_dir.glob("*.yml")))
        if not artifact_paths:
            return CompiledContractLoadResult(
                diagnostics=(_missing_artifacts_diagnostic(compiled_contracts_dir),)
            )

        return self._load_paths(artifact_paths)

    def load_for_compiled_checks(
        self,
        target_path: Path,
        check_artifacts: tuple[LoadedCompiledChecksArtifact, ...],
    ) -> CompiledContractLoadResult:
        """Load compiled contracts referenced by loaded compiled-check artifacts."""
        compiled_contracts_dir = target_path / COMPILED_CONTRACTS_DIR_NAME
        directory_diagnostic = _compiled_contracts_directory_diagnostic(compiled_contracts_dir)
        if directory_diagnostic is not None:
            return CompiledContractLoadResult(diagnostics=(directory_diagnostic,))

        artifact_paths: list[Path] = []
        diagnostics: list[Diagnostic] = []
        seen_contract_names: set[str] = set()
        for check_artifact in check_artifacts:
            if check_artifact.contract_name in seen_contract_names:
                continue
            seen_contract_names.add(check_artifact.contract_name)
            artifact_path, reference_diagnostic = _referenced_compiled_contract_artifact_path(
                compiled_contracts_dir,
                check_artifact,
            )
            if reference_diagnostic is not None:
                diagnostics.append(reference_diagnostic)
                continue
            assert artifact_path is not None
            path_diagnostic = _symlinked_artifact_path_diagnostic(artifact_path)
            if path_diagnostic is not None:
                diagnostics.append(path_diagnostic)
                continue
            if not artifact_path.exists():
                diagnostics.append(_missing_artifacts_diagnostic(artifact_path))
                continue
            artifact_paths.append(artifact_path)

        if diagnostics:
            return CompiledContractLoadResult(diagnostics=tuple(diagnostics))
        load_result = self._load_paths(tuple(artifact_paths))
        if not load_result.succeeded:
            return load_result

        mismatch_diagnostics = _reference_mismatch_diagnostics(
            load_result.artifacts,
            check_artifacts,
        )
        if mismatch_diagnostics:
            return CompiledContractLoadResult(diagnostics=mismatch_diagnostics)
        return load_result

    def _load_paths(
        self,
        artifact_paths: tuple[Path, ...],
    ) -> CompiledContractLoadResult:
        artifacts: list[LoadedCompiledContractArtifact] = []
        diagnostics: list[Diagnostic] = []
        seen_contract_ids: set[str] = set()
        seen_contract_names: set[str] = set()

        for artifact_path in artifact_paths:
            artifact, artifact_diagnostics = self._load_artifact(
                artifact_path,
                seen_contract_ids=seen_contract_ids,
                seen_contract_names=seen_contract_names,
            )
            diagnostics.extend(artifact_diagnostics)
            if artifact is not None:
                artifacts.append(artifact)

        if diagnostics:
            return CompiledContractLoadResult(diagnostics=tuple(diagnostics))
        return CompiledContractLoadResult(artifacts=tuple(artifacts))

    def _load_artifact(
        self,
        artifact_path: Path,
        *,
        seen_contract_ids: set[str],
        seen_contract_names: set[str],
    ) -> tuple[LoadedCompiledContractArtifact | None, tuple[Diagnostic, ...]]:
        path_diagnostic = _symlinked_artifact_path_diagnostic(artifact_path)
        if path_diagnostic is not None:
            return None, (path_diagnostic,)
        try:
            payload = _read_yaml_mapping(artifact_path)
            artifact = _parse_artifact(
                artifact_path,
                payload,
                seen_contract_ids=seen_contract_ids,
                seen_contract_names=seen_contract_names,
            )
        except yaml.YAMLError:
            return None, (
                _invalid_artifact_diagnostic(
                    artifact_path,
                    "Compiled-contract artifact is invalid YAML.",
                ),
            )
        except (OSError, UnicodeDecodeError):
            return None, (
                _invalid_artifact_diagnostic(
                    artifact_path,
                    "Compiled-contract artifact could not be read.",
                ),
            )
        except _ArtifactShapeError as error:
            return None, (_invalid_artifact_diagnostic(artifact_path, str(error)),)

        return artifact, ()


def _compiled_contracts_directory_diagnostic(path: Path) -> Diagnostic | None:
    path_diagnostic = _symlinked_artifact_path_diagnostic(path)
    if path_diagnostic is not None:
        return path_diagnostic
    if not path.exists():
        return _missing_artifacts_diagnostic(path)
    if not path.is_dir() or path.is_symlink():
        return _invalid_artifact_diagnostic(
            path,
            "Compiled-contract artifact path is not a real directory.",
        )
    return None


def _referenced_compiled_contract_artifact_path(
    compiled_contracts_dir: Path,
    check_artifact: LoadedCompiledChecksArtifact,
) -> tuple[Path | None, Diagnostic | None]:
    if not _is_safe_artifact_name_stem(check_artifact.contract_name):
        return None, _invalid_artifact_diagnostic(
            check_artifact.path,
            "Compiled-check artifact contains an unsafe compiled contract reference.",
        )
    return compiled_contracts_dir / f"{check_artifact.contract_name}.yml", None


def _is_safe_artifact_name_stem(value: str) -> bool:
    return (
        value not in {".", ".."}
        and not Path(value).is_absolute()
        and "/" not in value
        and "\\" not in value
    )


def _read_yaml_mapping(path: Path) -> dict[str, object]:
    loaded = load_yaml_with_unique_keys(path.read_text(encoding="utf-8"))
    return dict(_as_mapping(loaded, "artifact root"))


def _symlinked_artifact_path_diagnostic(path: Path) -> Diagnostic | None:
    try:
        reject_symlinked_path_components(path)
    except FileExistsError:
        return _invalid_artifact_diagnostic(
            path,
            "Compiled-contract artifact path contains a symlink.",
        )
    return None


def _parse_artifact(
    path: Path,
    payload: dict[str, object],
    *,
    seen_contract_ids: set[str],
    seen_contract_names: set[str],
) -> LoadedCompiledContractArtifact:
    artifact_type = _required_string(payload, "artifact_type", "artifact_type")
    if artifact_type != "compiled_contract":
        raise _ArtifactShapeError(
            "Compiled-contract artifact field artifact_type must be compiled_contract."
        )

    artifact_version = _required_int(payload, "artifact_version", "artifact_version")
    if artifact_version != COMPILED_ARTIFACT_VERSION:
        raise _ArtifactShapeError(
            "Compiled-contract artifact field artifact_version is not supported."
        )

    project = _required_mapping(payload, "project", "project")
    project_name = _required_string(project, "name", "project.name")
    project_version = _optional_string(project, "version", "project.version")

    contract = _required_mapping(payload, "contract", "contract")
    contract_id = _required_string(contract, "id", "contract.id")
    if contract_id in seen_contract_ids:
        raise _ArtifactShapeError(
            f"Compiled-contract artifact contains duplicate contract id: {contract_id}."
        )
    seen_contract_ids.add(contract_id)

    contract_name = _required_string(contract, "name", "contract.name")
    if contract_name in seen_contract_names:
        raise _ArtifactShapeError(
            f"Compiled-contract artifact contains duplicate contract name: {contract_name}."
        )
    seen_contract_names.add(contract_name)

    source_file = _required_string(contract, "source_file", "contract.source_file")
    source = _parse_endpoint(_required_mapping(payload, "source", "source"), path="source")
    target = _parse_endpoint(_required_mapping(payload, "target", "target"), path="target")
    grain_keys = _parse_grain_keys(_required_mapping(payload, "identity", "identity"))
    diagnostics = _parse_diagnostics(payload.get("diagnostics"), "diagnostics")

    return LoadedCompiledContractArtifact(
        path=path,
        project_name=project_name,
        project_version=project_version,
        contract_id=contract_id,
        contract_name=contract_name,
        source_file=source_file,
        source=source,
        target=target,
        grain_keys=grain_keys,
        diagnostics=diagnostics,
    )


def _parse_endpoint(endpoint: Mapping[str, object], *, path: str) -> LoadedCompiledEndpoint:
    connection = _required_string(endpoint, "connection", f"{path}.connection")
    relation = _optional_string(endpoint, "relation", f"{path}.relation")
    query = _optional_string(endpoint, "query", f"{path}.query")
    if (relation is None and query is None) or (relation is not None and query is not None):
        raise _ArtifactShapeError(
            f"Compiled-contract artifact field {path} must define exactly one of relation or query."
        )
    return LoadedCompiledEndpoint(connection=connection, relation=relation, query=query)


def _parse_grain_keys(identity: Mapping[str, object]) -> tuple[str, ...]:
    grain = _required_mapping(identity, "grain", "identity.grain")
    return _required_string_tuple(grain, "keys", "identity.grain.keys")


def _reference_mismatch_diagnostics(
    contracts: tuple[LoadedCompiledContractArtifact, ...],
    check_artifacts: tuple[LoadedCompiledChecksArtifact, ...],
) -> tuple[Diagnostic, ...]:
    contracts_by_name = {contract.contract_name: contract for contract in contracts}
    diagnostics: list[Diagnostic] = []

    for check_artifact in check_artifacts:
        contract = contracts_by_name.get(check_artifact.contract_name)
        if contract is None:
            diagnostics.append(
                _invalid_artifact_diagnostic(
                    check_artifact.path,
                    "Compiled-check artifact references a compiled contract that was not loaded.",
                )
            )
            continue
        if (
            contract.contract_id != check_artifact.contract_id
            or contract.contract_name != check_artifact.contract_name
            or contract.source_file != check_artifact.source_file
            or contract.project_name != check_artifact.project_name
            or contract.project_version != check_artifact.project_version
        ):
            diagnostics.append(
                _invalid_artifact_diagnostic(
                    contract.path,
                    (
                        "Compiled-contract artifact identity does not match the "
                        "compiled-check artifact reference."
                    ),
                )
            )

    return tuple(diagnostics)


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
            f"Compiled-contract artifact field {path}.severity is invalid."
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
        raise _ArtifactShapeError(f"Compiled-contract artifact is missing field {path}.")
    return _as_mapping(mapping[key], path)


def _required_string(mapping: Mapping[str, object], key: str, path: str) -> str:
    if key not in mapping:
        raise _ArtifactShapeError(f"Compiled-contract artifact is missing field {path}.")
    value = mapping[key]
    if not isinstance(value, str) or not value:
        raise _ArtifactShapeError(f"Compiled-contract artifact field {path} must be a string.")
    return value


def _optional_string(mapping: Mapping[str, object], key: str, path: str) -> str | None:
    if key not in mapping or mapping[key] is None:
        return None
    value = mapping[key]
    if not isinstance(value, str) or not value:
        raise _ArtifactShapeError(f"Compiled-contract artifact field {path} must be a string.")
    return value


def _required_int(mapping: Mapping[str, object], key: str, path: str) -> int:
    if key not in mapping:
        raise _ArtifactShapeError(f"Compiled-contract artifact is missing field {path}.")
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise _ArtifactShapeError(f"Compiled-contract artifact field {path} must be an integer.")
    return value


def _optional_int(mapping: Mapping[str, object], key: str, path: str) -> int | None:
    if key not in mapping or mapping[key] is None:
        return None
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise _ArtifactShapeError(f"Compiled-contract artifact field {path} must be an integer.")
    return value


def _required_string_tuple(
    mapping: Mapping[str, object],
    key: str,
    path: str,
) -> tuple[str, ...]:
    return _string_tuple(_required_list(mapping, key, path), path)


def _required_list(mapping: Mapping[str, object], key: str, path: str) -> list[object]:
    if key not in mapping:
        raise _ArtifactShapeError(f"Compiled-contract artifact is missing field {path}.")
    return _as_list(mapping[key], path)


def _string_tuple(values: list[object], path: str) -> tuple[str, ...]:
    strings: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value:
            raise _ArtifactShapeError(
                f"Compiled-contract artifact field {path}[{index}] must be a string."
            )
        strings.append(value)
    return tuple(strings)


def _as_mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise _ArtifactShapeError(f"Compiled-contract artifact field {path} must be a mapping.")
    if any(not isinstance(key, str) for key in value):
        raise _ArtifactShapeError(f"Compiled-contract artifact field {path} must use string keys.")
    return cast(Mapping[str, object], value)


def _as_list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise _ArtifactShapeError(f"Compiled-contract artifact field {path} must be a list.")
    return cast(list[object], value)


def _missing_artifacts_diagnostic(path: Path) -> Diagnostic:
    return Diagnostic(
        code=COMPILED_CONTRACT_ARTIFACT_NOT_FOUND,
        severity=DiagnosticSeverity.ERROR,
        message="Expected compiled-contract artifacts are missing.",
        resource_type="compiled_contract_artifact",
        path=str(path),
        hint="Run `recon compile` before `recon run`.",
    )


def _invalid_artifact_diagnostic(path: Path, message: str) -> Diagnostic:
    return Diagnostic(
        code=COMPILED_CONTRACT_ARTIFACT_INVALID,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="compiled_contract_artifact",
        path=str(path),
        hint="Regenerate compiled contract artifacts with `recon compile`.",
    )
