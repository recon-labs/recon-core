"""Shared parsed-project loading for authored Recon resources."""

from dataclasses import dataclass, replace

from recon_core.diagnostics import Diagnostic
from recon_core.parser.contracts import AuthoredContract, parse_contract_resource
from recon_core.parser.files import ResourceFile, discover_contract_files
from recon_core.parser.yaml_loader import load_yaml_file
from recon_core.project import ProjectContext


@dataclass(frozen=True, slots=True)
class ParsedProject:
    """Parsed authored project resources and diagnostics."""

    context: ProjectContext
    files: tuple[ResourceFile, ...] = ()
    contracts: tuple[AuthoredContract, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not self.diagnostics


def load_parsed_project(context: ProjectContext) -> ParsedProject:
    """Load authored contract resources into parsed in-memory models."""
    discovery_result = discover_contract_files(
        context.project_root,
        context.paths.contract_paths,
    )
    diagnostics = list(discovery_result.diagnostics)
    contracts = _parse_contract_files(discovery_result.files, diagnostics)

    return ParsedProject(
        context=context,
        files=discovery_result.files,
        contracts=tuple(contracts),
        diagnostics=tuple(diagnostics),
    )


def _parse_contract_files(
    resource_files: tuple[ResourceFile, ...],
    diagnostics: list[Diagnostic],
) -> list[AuthoredContract]:
    contracts: list[AuthoredContract] = []

    for resource_file in resource_files:
        yaml_result = load_yaml_file(resource_file.path)
        diagnostics.extend(_resource_relative_diagnostics(yaml_result.diagnostics, resource_file))
        if not yaml_result.succeeded:
            continue

        contract_result = parse_contract_resource(resource_file, yaml_result.data)
        diagnostics.extend(contract_result.diagnostics)
        contracts.extend(contract_result.contracts)

    return contracts


def _resource_relative_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    resource_file: ResourceFile,
) -> tuple[Diagnostic, ...]:
    return tuple(
        replace(diagnostic, path=resource_file.relative_path) for diagnostic in diagnostics
    )
