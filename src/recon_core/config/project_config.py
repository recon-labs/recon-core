"""Project configuration loading."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

INVALID_PROJECT_YAML = "RC_CONFIG_INVALID_PROJECT_YAML"
INVALID_PROJECT_CONFIG = "RC_CONFIG_INVALID_PROJECT_CONFIG"

_ALLOWED_FIELDS = frozenset(
    {
        "name",
        "version",
        "config-version",
        "profile",
        "contract-paths",
        "sample-policy-paths",
        "tolerance-policy-paths",
        "schema-policy-paths",
        "check-pack-paths",
        "macro-paths",
        "target-path",
        "report-path",
        "state-path",
    }
)

_PATH_LIST_DEFAULTS: dict[str, tuple[str, ...]] = {
    "contract-paths": ("contracts",),
    "sample-policy-paths": ("sample_policies",),
    "tolerance-policy-paths": ("tolerances",),
    "schema-policy-paths": ("schema_policies",),
    "check-pack-paths": ("check_packs",),
    "macro-paths": ("macros",),
}

_SCALAR_PATH_DEFAULTS: dict[str, str] = {
    "target-path": "target",
    "report-path": "reports",
    "state-path": "state",
}


class _UniqueKeySafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    """YAML safe loader that rejects duplicate mapping keys."""


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Typed project configuration from recon_project.yml."""

    name: str
    version: str | None
    config_version: int
    profile: str | None
    contract_paths: tuple[str, ...]
    sample_policy_paths: tuple[str, ...]
    tolerance_policy_paths: tuple[str, ...]
    schema_policy_paths: tuple[str, ...]
    check_pack_paths: tuple[str, ...]
    macro_paths: tuple[str, ...]
    target_path: str
    report_path: str
    state_path: str


@dataclass(frozen=True, slots=True)
class ProjectConfigLoadResult:
    """Result for project config loading."""

    config: ProjectConfig | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.config is not None and not self.diagnostics


def load_project_config(project_file: Path) -> ProjectConfigLoadResult:
    """Load and validate a Recon project config file."""
    try:
        raw_content = project_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ProjectConfigLoadResult(
            diagnostics=(
                _invalid_config_diagnostic(
                    project_file,
                    f"Project config file does not exist: {project_file}",
                    hint="Run this command from a Recon project directory.",
                ),
            )
        )
    except OSError as error:
        return ProjectConfigLoadResult(
            diagnostics=(
                _invalid_config_diagnostic(
                    project_file,
                    f"Could not read project config file: {project_file}",
                    hint=f"Check that the path points to a readable file. Error: {error}",
                ),
            )
        )

    try:
        loaded: object = yaml.load(raw_content, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as error:
        return ProjectConfigLoadResult(diagnostics=(_invalid_yaml_diagnostic(project_file, error),))

    raw_config, diagnostic = _coerce_project_mapping(loaded, project_file)
    if diagnostic is not None:
        return ProjectConfigLoadResult(diagnostics=(diagnostic,))

    assert raw_config is not None
    return _project_config_from_mapping(raw_config, project_file)


def _construct_mapping_without_duplicate_keys(
    loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}

    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = key_node.start_mark
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"Duplicate YAML key: {key}",
                mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)

    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicate_keys,
)


def _coerce_project_mapping(
    loaded: object, project_file: Path
) -> tuple[dict[str, object] | None, Diagnostic | None]:
    if not isinstance(loaded, dict):
        return None, _invalid_config_diagnostic(
            project_file,
            "recon_project.yml must contain a top-level mapping.",
            hint="Use key-value YAML entries such as `name: ecommerce_recon`.",
        )

    config: dict[str, object] = {}
    for key, value in loaded.items():
        if not isinstance(key, str):
            return None, _invalid_config_diagnostic(
                project_file,
                "recon_project.yml keys must be strings.",
                hint="Use documented project config field names.",
            )
        config[key] = value

    return config, None


def _project_config_from_mapping(
    raw_config: dict[str, object], project_file: Path
) -> ProjectConfigLoadResult:
    diagnostics = _validate_unknown_fields(raw_config, project_file)

    name = _required_string(raw_config, "name", project_file, diagnostics)
    version = _optional_string(raw_config, "version", project_file, diagnostics)
    profile = _optional_string(raw_config, "profile", project_file, diagnostics)
    config_version = _integer(raw_config, "config-version", 1, project_file, diagnostics)

    contract_paths = _path_list(raw_config, "contract-paths", project_file, diagnostics)
    sample_policy_paths = _path_list(raw_config, "sample-policy-paths", project_file, diagnostics)
    tolerance_policy_paths = _path_list(
        raw_config, "tolerance-policy-paths", project_file, diagnostics
    )
    schema_policy_paths = _path_list(raw_config, "schema-policy-paths", project_file, diagnostics)
    check_pack_paths = _path_list(raw_config, "check-pack-paths", project_file, diagnostics)
    macro_paths = _path_list(raw_config, "macro-paths", project_file, diagnostics)

    target_path = _string_with_default(raw_config, "target-path", project_file, diagnostics)
    report_path = _string_with_default(raw_config, "report-path", project_file, diagnostics)
    state_path = _string_with_default(raw_config, "state-path", project_file, diagnostics)

    if diagnostics:
        return ProjectConfigLoadResult(diagnostics=tuple(diagnostics))

    return ProjectConfigLoadResult(
        config=ProjectConfig(
            name=name,
            version=version,
            config_version=config_version,
            profile=profile,
            contract_paths=contract_paths,
            sample_policy_paths=sample_policy_paths,
            tolerance_policy_paths=tolerance_policy_paths,
            schema_policy_paths=schema_policy_paths,
            check_pack_paths=check_pack_paths,
            macro_paths=macro_paths,
            target_path=target_path,
            report_path=report_path,
            state_path=state_path,
        )
    )


def _validate_unknown_fields(raw_config: dict[str, object], project_file: Path) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    unknown_fields = sorted(set(raw_config) - _ALLOWED_FIELDS)

    for field_name in unknown_fields:
        diagnostics.append(
            _invalid_config_diagnostic(
                project_file,
                f"Unknown project config field: {field_name}",
                hint="Remove the field or use a documented recon_project.yml field.",
            )
        )

    return diagnostics


def _required_string(
    raw_config: dict[str, object],
    field_name: str,
    project_file: Path,
    diagnostics: list[Diagnostic],
) -> str:
    value = raw_config.get(field_name)
    if value is None:
        diagnostics.append(
            _invalid_config_diagnostic(
                project_file,
                f"Missing required project config field: {field_name}",
                hint=f"Add `{field_name}: <value>` to recon_project.yml.",
            )
        )
        return ""

    string_value = _string_value(value, field_name, project_file, diagnostics)
    if string_value == "":
        diagnostics.append(
            _invalid_config_diagnostic(
                project_file,
                f"Project config field `{field_name}` cannot be empty.",
                hint=f"Set `{field_name}` to a non-empty string.",
            )
        )

    return string_value


def _optional_string(
    raw_config: dict[str, object],
    field_name: str,
    project_file: Path,
    diagnostics: list[Diagnostic],
) -> str | None:
    if field_name not in raw_config or raw_config[field_name] is None:
        return None

    value = _string_value(raw_config[field_name], field_name, project_file, diagnostics)
    if value == "":
        diagnostics.append(
            _invalid_config_diagnostic(
                project_file,
                f"Project config field `{field_name}` cannot be empty.",
                hint=f"Set `{field_name}` to a non-empty string or remove it.",
            )
        )

    return value


def _integer(
    raw_config: dict[str, object],
    field_name: str,
    default: int,
    project_file: Path,
    diagnostics: list[Diagnostic],
) -> int:
    value = raw_config.get(field_name, default)
    if type(value) is not int:
        diagnostics.append(
            _invalid_config_diagnostic(
                project_file,
                f"Project config field `{field_name}` must be an integer.",
                hint=f"Set `{field_name}` to an integer value.",
            )
        )
        return default

    return value


def _path_list(
    raw_config: dict[str, object],
    field_name: str,
    project_file: Path,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    value = raw_config.get(field_name, _PATH_LIST_DEFAULTS[field_name])
    if not isinstance(value, list | tuple):
        diagnostics.append(
            _invalid_config_diagnostic(
                project_file,
                f"Project config field `{field_name}` must be a list of strings.",
                hint=f"Use `{field_name}: [path_name]` or a YAML list.",
            )
        )
        return _PATH_LIST_DEFAULTS[field_name]

    paths: list[str] = []
    for item in value:
        if not isinstance(item, str) or item == "":
            diagnostics.append(
                _invalid_config_diagnostic(
                    project_file,
                    f"Project config field `{field_name}` must contain only non-empty strings.",
                    hint=f"Remove invalid entries from `{field_name}`.",
                )
            )
            return _PATH_LIST_DEFAULTS[field_name]
        paths.append(item)

    return tuple(paths)


def _string_with_default(
    raw_config: dict[str, object],
    field_name: str,
    project_file: Path,
    diagnostics: list[Diagnostic],
) -> str:
    value = raw_config.get(field_name, _SCALAR_PATH_DEFAULTS[field_name])
    string_value = _string_value(value, field_name, project_file, diagnostics)
    if string_value == "":
        diagnostics.append(
            _invalid_config_diagnostic(
                project_file,
                f"Project config field `{field_name}` cannot be empty.",
                hint=f"Set `{field_name}` to a non-empty path string.",
            )
        )
        return _SCALAR_PATH_DEFAULTS[field_name]

    return string_value


def _string_value(
    value: object,
    field_name: str,
    project_file: Path,
    diagnostics: list[Diagnostic],
) -> str:
    if not isinstance(value, str):
        diagnostics.append(
            _invalid_config_diagnostic(
                project_file,
                f"Project config field `{field_name}` must be a string.",
                hint=f"Set `{field_name}` to a string value.",
            )
        )
        return ""

    return value


def _invalid_yaml_diagnostic(project_file: Path, error: yaml.YAMLError) -> Diagnostic:
    mark = getattr(error, "problem_mark", None)
    line = mark.line + 1 if mark is not None else None
    column = mark.column + 1 if mark is not None else None

    return Diagnostic(
        code=INVALID_PROJECT_YAML,
        severity=DiagnosticSeverity.ERROR,
        message=f"Invalid YAML in project config: {error}",
        resource_type="project_config",
        path=str(project_file),
        line=line,
        column=column,
        hint="Fix the YAML syntax in recon_project.yml.",
    )


def _invalid_config_diagnostic(
    project_file: Path, message: str, *, hint: str | None = None
) -> Diagnostic:
    return Diagnostic(
        code=INVALID_PROJECT_CONFIG,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="project_config",
        path=str(project_file),
        hint=hint,
    )
