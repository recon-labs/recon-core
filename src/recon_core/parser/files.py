"""Resource file discovery for authored Recon project files."""

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import TypedDict

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

RESOURCE_PATH_NOT_FOUND = "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
_YAML_SUFFIXES = frozenset({".yaml", ".yml"})


class ResourceType(StrEnum):
    """Authored resource file categories."""

    CONTRACT = "contract"


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
    diagnostics: list[Diagnostic] = []
    discovered_by_real_path: dict[Path, ResourceFile] = {}

    for contract_path in contract_paths:
        if not contract_path.exists():
            diagnostics.append(
                _missing_contract_path_diagnostic(
                    contract_path,
                    f"Configured contract path does not exist: {contract_path}",
                )
            )
            continue

        if not contract_path.is_dir():
            diagnostics.append(
                _missing_contract_path_diagnostic(
                    contract_path,
                    f"Configured contract path must be a directory: {contract_path}",
                )
            )
            continue

        for path in _iter_yaml_files(contract_path):
            real_path = path.resolve()
            if real_path in discovered_by_real_path:
                continue
            discovered_by_real_path[real_path] = ResourceFile(
                path=path,
                relative_path=_relative_posix_path(project_root, path),
                resource_type=ResourceType.CONTRACT,
                checksum=_file_checksum(path),
            )

    files = tuple(
        sorted(
            discovered_by_real_path.values(),
            key=lambda resource: resource.relative_path,
        )
    )

    return ResourceDiscoveryResult(files=files, diagnostics=tuple(diagnostics))


def _iter_yaml_files(path: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix.lower() in _YAML_SUFFIXES
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


def _missing_contract_path_diagnostic(path: Path, message: str) -> Diagnostic:
    return Diagnostic(
        code=RESOURCE_PATH_NOT_FOUND,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="contract_path",
        path=str(path),
        hint="Create the directory or update `contract-paths`.",
    )
