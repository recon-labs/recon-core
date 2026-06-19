"""YAML loading helpers for authored Recon resources."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from recon_core._yaml import (
    load_yaml_with_unique_keys,
    safe_yaml_error_message,
    yaml_error_position,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

INVALID_YAML = "RC_PARSE_INVALID_YAML"
YAML_FILE_READ_ERROR = "RC_PARSE_FILE_READ_ERROR"


@dataclass(frozen=True, slots=True)
class YamlLoadResult:
    """Result for loading a YAML resource."""

    data: object | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not self.diagnostics


def load_yaml_file(path: Path) -> YamlLoadResult:
    """Load a YAML resource file from disk."""
    try:
        raw_content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return YamlLoadResult(
            diagnostics=(
                Diagnostic(
                    code=YAML_FILE_READ_ERROR,
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Could not read YAML resource file: {path}. Error: {error}",
                    resource_type="resource_file",
                    path=str(path),
                    hint="Check that the resource file exists and is readable.",
                ),
            )
        )

    return load_yaml_text(raw_content, path=str(path))


def load_yaml_text(content: str, *, path: str) -> YamlLoadResult:
    """Load YAML resource text with duplicate-key protection."""
    try:
        loaded = load_yaml_with_unique_keys(content)
    except yaml.YAMLError as error:
        return YamlLoadResult(diagnostics=(_invalid_yaml_diagnostic(path, error),))

    return YamlLoadResult(data=loaded)


def _invalid_yaml_diagnostic(path: str, error: yaml.YAMLError) -> Diagnostic:
    line, column = yaml_error_position(error)

    return Diagnostic(
        code=INVALID_YAML,
        severity=DiagnosticSeverity.ERROR,
        message=safe_yaml_error_message("Invalid YAML in resource file", error),
        resource_type="resource_file",
        path=path,
        line=line,
        column=column,
        hint="Fix the YAML syntax in this resource file.",
    )
