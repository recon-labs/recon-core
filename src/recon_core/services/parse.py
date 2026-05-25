"""Parse command service."""

from dataclasses import dataclass
from pathlib import Path

from recon_core.artifacts import ManifestWriter
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.parser import ManifestProject, build_manifest, load_parsed_project
from recon_core.project import load_project_context
from recon_core.services.results import ExitCategory, ServiceResult

MANIFEST_WRITE_FAILED = "RC_RUNTIME_MANIFEST_WRITE_FAILED"


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

        parsed_project = load_parsed_project(context)

        manifest = build_manifest(
            project=ManifestProject(
                name=context.config.name,
                config_version=context.config.config_version,
                version=context.config.version,
            ),
            files=parsed_project.files,
            contracts=parsed_project.contracts,
            diagnostics=parsed_project.diagnostics,
        )
        try:
            manifest_path = ManifestWriter().write(manifest, context.paths.target_path)
        except OSError as exc:
            target_path = _display_path(context.paths.target_path, context.project_root)
            return ServiceResult(
                exit_category=ExitCategory.RUNTIME_ERROR,
                message="Parse completed but manifest could not be written.",
                diagnostics=(
                    Diagnostic(
                        code=MANIFEST_WRITE_FAILED,
                        severity=DiagnosticSeverity.ERROR,
                        message=f"Unable to write manifest to {target_path}: {exc}",
                        resource_type="manifest",
                        path=target_path,
                        hint=(
                            "Check that target-path is a writable directory "
                            "or update target-path in recon_project.yml."
                        ),
                    ),
                ),
            )

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


def _pluralize(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)
