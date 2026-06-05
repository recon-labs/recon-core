"""YAML loading helpers for authored Recon resources."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

INVALID_YAML = "RC_PARSE_INVALID_YAML"
YAML_FILE_READ_ERROR = "RC_PARSE_FILE_READ_ERROR"


class _UniqueKeySafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    """YAML safe loader that rejects duplicate mapping keys."""


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
        loaded: object = yaml.load(content, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as error:
        return YamlLoadResult(diagnostics=(_invalid_yaml_diagnostic(path, error),))

    return YamlLoadResult(data=loaded)


def _construct_mapping_without_duplicate_keys(
    loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}

    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            hash(key)
        except TypeError as error:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"Unsupported YAML mapping key: {key}",
                key_node.start_mark,
            ) from error

        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"Duplicate YAML key: {key}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)

    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicate_keys,
)


def _invalid_yaml_diagnostic(path: str, error: yaml.YAMLError) -> Diagnostic:
    mark = getattr(error, "problem_mark", None)
    line = mark.line + 1 if mark is not None else None
    column = mark.column + 1 if mark is not None else None

    return Diagnostic(
        code=INVALID_YAML,
        severity=DiagnosticSeverity.ERROR,
        message=_safe_yaml_error_message("Invalid YAML in resource file", error),
        resource_type="resource_file",
        path=path,
        line=line,
        column=column,
        hint="Fix the YAML syntax in this resource file.",
    )


def _safe_yaml_error_message(prefix: str, error: yaml.YAMLError) -> str:
    problem = getattr(error, "problem", None)
    if isinstance(problem, str):
        if problem.startswith("Duplicate YAML key:"):
            return f"{prefix}: duplicate YAML key."
        if problem.startswith("Unsupported YAML mapping key:"):
            return f"{prefix}: unsupported YAML mapping key."
    return f"{prefix}."
