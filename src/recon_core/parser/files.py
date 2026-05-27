"""Resource file discovery for authored Recon project files."""

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import TypedDict

from recon_core.config import PathOrigin
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.project import ResolvedResourcePath

RESOURCE_PATH_NOT_FOUND = "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
_YAML_SUFFIXES = frozenset({".yaml", ".yml"})


class ResourceType(StrEnum):
    """Authored resource file categories."""

    CONTRACT = "contract"
    CHECK_PACK = "check_pack"
    SAMPLE_POLICY = "sample_policy"
    TOLERANCE_POLICY = "tolerance_policy"
    SCHEMA_POLICY = "schema_policy"
    MACRO_FILE = "macro_file"


@dataclass(frozen=True, slots=True)
class ResourceKindDefinition:
    """Catalog entry for an authored project resource file kind."""

    resource_type: ResourceType
    path_field: str
    suffixes: frozenset[str]
    required_by_default: bool
    explicit_missing_is_error: bool
    handling: str


LOCAL_RESOURCE_KIND_DEFINITIONS: tuple[ResourceKindDefinition, ...] = (
    ResourceKindDefinition(
        resource_type=ResourceType.CONTRACT,
        path_field="contract-paths",
        suffixes=_YAML_SUFFIXES,
        required_by_default=True,
        explicit_missing_is_error=True,
        handling="parse",
    ),
    ResourceKindDefinition(
        resource_type=ResourceType.CHECK_PACK,
        path_field="check-pack-paths",
        suffixes=_YAML_SUFFIXES,
        required_by_default=False,
        explicit_missing_is_error=True,
        handling="index",
    ),
    ResourceKindDefinition(
        resource_type=ResourceType.SAMPLE_POLICY,
        path_field="sample-policy-paths",
        suffixes=_YAML_SUFFIXES,
        required_by_default=False,
        explicit_missing_is_error=True,
        handling="index",
    ),
    ResourceKindDefinition(
        resource_type=ResourceType.TOLERANCE_POLICY,
        path_field="tolerance-policy-paths",
        suffixes=_YAML_SUFFIXES,
        required_by_default=False,
        explicit_missing_is_error=True,
        handling="index",
    ),
    ResourceKindDefinition(
        resource_type=ResourceType.SCHEMA_POLICY,
        path_field="schema-policy-paths",
        suffixes=_YAML_SUFFIXES,
        required_by_default=False,
        explicit_missing_is_error=True,
        handling="index",
    ),
    ResourceKindDefinition(
        resource_type=ResourceType.MACRO_FILE,
        path_field="macro-paths",
        suffixes=frozenset({".sql"}),
        required_by_default=False,
        explicit_missing_is_error=True,
        handling="index",
    ),
)


class ResourceFileDict(TypedDict):
    path: str
    resource_type: str
    checksum: str


@dataclass(frozen=True, slots=True)
class ResourceFile:
    """Discovered authored resource file."""

    path: Path
    relative_path: str
    resource_type: ResourceType
    checksum: str

    def to_dict(self) -> ResourceFileDict:
        return {
            "path": self.relative_path,
            "resource_type": self.resource_type.value,
            "checksum": self.checksum,
        }


@dataclass(frozen=True, slots=True)
class ResourceDiscoveryResult:
    """Result for resource file discovery."""

    files: tuple[ResourceFile, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not self.diagnostics


def discover_contract_files(
    project_root: Path, contract_paths: tuple[Path, ...]
) -> ResourceDiscoveryResult:
    """Discover contract YAML files from configured contract paths."""
    return discover_resource_files(
        project_root,
        tuple(
            ResolvedResourcePath(
                path=contract_path,
                origin=PathOrigin.AUTHORED,
                field_name="contract-paths",
            )
            for contract_path in contract_paths
        ),
        definitions=(LOCAL_RESOURCE_KIND_DEFINITIONS[0],),
    )


def discover_resource_files(
    project_root: Path,
    resource_paths: tuple[ResolvedResourcePath, ...],
    *,
    definitions: tuple[ResourceKindDefinition, ...] = LOCAL_RESOURCE_KIND_DEFINITIONS,
) -> ResourceDiscoveryResult:
    """Discover authored resource files from cataloged project resource paths."""
    diagnostics: list[Diagnostic] = []
    discovered_by_real_path: dict[Path, ResourceFile] = {}
    definitions_by_field = {definition.path_field: definition for definition in definitions}

    for resource_path in resource_paths:
        definition = definitions_by_field.get(resource_path.field_name)
        if definition is None:
            continue

        if not resource_path.path.exists():
            if _missing_path_is_allowed(resource_path, definition):
                continue
            diagnostics.append(
                _missing_resource_path_diagnostic(
                    resource_path,
                    definition,
                    f"Configured {definition.path_field} path does not exist: {resource_path.path}",
                )
            )
            continue

        if not resource_path.path.is_dir():
            message = (
                f"Configured {definition.path_field} path must be a directory: {resource_path.path}"
            )
            diagnostics.append(
                _missing_resource_path_diagnostic(
                    resource_path,
                    definition,
                    message,
                )
            )
            continue

        for path in _iter_resource_files(resource_path.path, definition.suffixes):
            real_path = path.resolve()
            if real_path in discovered_by_real_path:
                continue
            discovered_by_real_path[real_path] = ResourceFile(
                path=path,
                relative_path=_relative_posix_path(project_root, path),
                resource_type=definition.resource_type,
                checksum=_file_checksum(path),
            )

    files = tuple(
        sorted(
            discovered_by_real_path.values(),
            key=lambda resource: resource.relative_path,
        )
    )

    return ResourceDiscoveryResult(files=files, diagnostics=tuple(diagnostics))


def _missing_path_is_allowed(
    resource_path: ResolvedResourcePath,
    definition: ResourceKindDefinition,
) -> bool:
    return resource_path.origin is PathOrigin.DEFAULTED and not definition.required_by_default


def _iter_yaml_files(path: Path) -> tuple[Path, ...]:
    return _iter_resource_files(path, _YAML_SUFFIXES)


def _iter_resource_files(path: Path, suffixes: frozenset[str]) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix.lower() in suffixes
            ),
            key=lambda candidate: candidate.as_posix(),
        )
    )


def _relative_posix_path(project_root: Path, path: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _file_checksum(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _missing_resource_path_diagnostic(
    resource_path: ResolvedResourcePath,
    definition: ResourceKindDefinition,
    message: str,
) -> Diagnostic:
    return Diagnostic(
        code=RESOURCE_PATH_NOT_FOUND,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type=f"{definition.resource_type.value}_path",
        path=str(resource_path.path),
        hint=f"Create the directory or update `{definition.path_field}`.",
    )
