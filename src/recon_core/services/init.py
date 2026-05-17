"""Init command service."""

from dataclasses import dataclass, field
from pathlib import Path

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services.results import ExitCategory, ServiceResult

PROJECT_CONFIG_TEMPLATE = """name: {project_name}
version: 0.1.0
config-version: 1

profile: dev

contract-paths:
  - contracts

sample-policy-paths:
  - sample_policies

tolerance-policy-paths:
  - tolerances

schema-policy-paths:
  - schema_policies

target-path: target
report-path: reports
state-path: state
"""

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
            PROJECT_CONFIG_TEMPLATE.format(project_name=self.project_name),
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
