"""Init command service."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import yaml

from recon_core.compiler.ids import STABLE_ID_PART_HINT, is_valid_stable_id_part
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services.results import ExitCategory, ServiceResult

PROFILES_EXAMPLE_TEMPLATE = """# Example Recon connection profiles.
# Copy this file to connections/profiles.yml for local use.
# Do not commit real profiles or secrets.

dev:
  target: example
  connections:
    example:
      type: postgres
      host: "{{ env_var('RECON_EXAMPLE_HOST') }}"
      port: "{{ env_var('RECON_EXAMPLE_PORT', '5432') }}"
      database: "{{ env_var('RECON_EXAMPLE_DATABASE') }}"
      user: "{{ env_var('RECON_EXAMPLE_USER') }}"
      password: "{{ env_var('RECON_EXAMPLE_PASSWORD') }}"
      schema: public
"""

GITIGNORE_TEMPLATE = """.env
connections/profiles.yml
target/
reports/
state/
recon_packages/
"""

PROJECT_DIRECTORIES = (
    "connections",
    "contracts",
    "check_packs",
    "macros",
    "sample_policies",
    "tolerances",
    "schema_policies",
    "target",
    "reports",
    "state",
)


@dataclass(frozen=True, slots=True)
class InitService:
    """Service boundary for recon init."""

    project_name: str
    base_dir: Path = field(default_factory=Path.cwd)

    def execute(self) -> ServiceResult:
        invalid_name_result = _validate_project_name(self.project_name)
        if invalid_name_result is not None:
            return invalid_name_result

        project_dir = self.base_dir / self.project_name
        if project_dir.exists():
            message = f"Path already exists: {project_dir}"
            return ServiceResult(
                exit_category=ExitCategory.CONFIGURATION_ERROR,
                message=message,
                diagnostics=(
                    Diagnostic(
                        code="RC_CONFIG_INIT_PATH_EXISTS",
                        severity=DiagnosticSeverity.ERROR,
                        message=message,
                        path=str(project_dir),
                        hint="Choose a new project name or remove the existing path.",
                    ),
                ),
            )

        project_dir.mkdir(parents=True)
        for directory in PROJECT_DIRECTORIES:
            (project_dir / directory).mkdir()

        self._write_text(
            project_dir / "recon_project.yml",
            _render_project_config(self.project_name),
        )
        self._write_text(
            project_dir / "connections" / "profiles.yml.example",
            PROFILES_EXAMPLE_TEMPLATE,
        )
        self._write_text(project_dir / ".gitignore", GITIGNORE_TEMPLATE)

        return ServiceResult.success(message=f"Created Recon project at {project_dir}")

    @staticmethod
    def _write_text(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")


def _render_project_config(project_name: str) -> str:
    project_config: dict[str, object] = {
        "name": project_name,
        "version": "0.1.0",
        "config-version": 1,
        "profile": "dev",
        "contract-paths": ["contracts"],
        "check-pack-paths": ["check_packs"],
        "macro-paths": ["macros"],
        "sample-policy-paths": ["sample_policies"],
        "tolerance-policy-paths": ["tolerances"],
        "schema-policy-paths": ["schema_policies"],
        "target-path": "target",
        "report-path": "reports",
        "state-path": "state",
    }

    return cast(str, yaml.safe_dump(project_config, sort_keys=False))


def _validate_project_name(project_name: str) -> ServiceResult | None:
    if _is_safe_project_name(project_name):
        return None

    message = f"Invalid project name: {project_name}"
    return ServiceResult(
        exit_category=ExitCategory.CONFIGURATION_ERROR,
        message=message,
        diagnostics=(
            Diagnostic(
                code="RC_CONFIG_INIT_INVALID_PROJECT_NAME",
                severity=DiagnosticSeverity.ERROR,
                message=message,
                resource_type="project",
                resource_name=project_name,
                hint=f"Use a single directory name. {STABLE_ID_PART_HINT}",
            ),
        ),
    )


def _is_safe_project_name(project_name: str) -> bool:
    if project_name in {"", ".", ".."}:
        return False
    if "/" in project_name or "\\" in project_name:
        return False
    return not Path(project_name).is_absolute() and is_valid_stable_id_part(project_name)
