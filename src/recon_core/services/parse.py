"""Parse command service."""

from dataclasses import dataclass, replace
from pathlib import Path

from recon_core.artifacts import ManifestWriter
from recon_core.diagnostics import Diagnostic
from recon_core.parser import (
    AuthoredContract,
    ManifestProject,
    ResourceFile,
    build_manifest,
    discover_contract_files,
    load_yaml_file,
    parse_contract_resource,
)
from recon_core.project import load_project_context
from recon_core.services.results import ExitCategory, ServiceResult


@dataclass(frozen=True, slots=True)
class ParseService:
    """Service boundary for recon parse."""

    start_path: Path | None = None

    def execute(self) -> ServiceResult:
        context_result = load_project_context(self.start_path)
        if not context_result.succeeded:
            return ServiceResult(
                exit_category=ExitCategory.CONFIGURATION_ERROR,
                message="Project configuration failed.",
                diagnostics=context_result.diagnostics,
            )

        assert context_result.context is not None
        context = context_result.context

        discovery_result = discover_contract_files(
            context.project_root,
            context.paths.contract_paths,
        )
        diagnostics = list(discovery_result.diagnostics)
        contracts = _parse_contract_files(discovery_result.files, diagnostics)

        manifest = build_manifest(
            project=ManifestProject(
                name=context.config.name,
                config_version=context.config.config_version,
                version=context.config.version,
            ),
            files=discovery_result.files,
            contracts=tuple(contracts),
            diagnostics=tuple(diagnostics),
        )
        manifest_path = ManifestWriter().write(manifest, context.paths.target_path)

        if manifest.succeeded:
            return ServiceResult.success(
                message=(
                    f"Parsed {_pluralize(len(manifest.contracts), 'contract')}. "
                    f"Wrote manifest to {manifest_path}."
                )
            )

        return ServiceResult(
            exit_category=ExitCategory.VALIDATION_ERROR,
            message=(
                f"Parse completed with {_pluralize(len(manifest.diagnostics), 'diagnostic')}. "
                f"Wrote manifest to {manifest_path}."
            ),
            diagnostics=manifest.diagnostics,
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


def _pluralize(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"
