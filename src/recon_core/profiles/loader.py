"""Connection profile loading for adapter-aware workflows."""

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.parser.contracts import AuthoredContract
from recon_core.profiles.models import ConnectionConfig, ProfileLoadResult, SelectedProfile
from recon_core.project import ProjectContext

PROFILE_FILE_NOT_FOUND = "RC_CONFIG_PROFILE_FILE_NOT_FOUND"
INVALID_PROFILE_YAML = "RC_CONFIG_INVALID_PROFILE_YAML"
INVALID_PROFILE_CONFIG = "RC_CONFIG_INVALID_PROFILE_CONFIG"
PROFILE_NOT_SELECTED = "RC_CONFIG_PROFILE_NOT_SELECTED"
PROFILE_NOT_FOUND = "RC_CONFIG_PROFILE_NOT_FOUND"
PROFILE_TARGET_NOT_FOUND = "RC_CONFIG_PROFILE_TARGET_NOT_FOUND"
PROFILE_CONNECTION_NOT_FOUND = "RC_CONFIG_PROFILE_CONNECTION_NOT_FOUND"
PROFILE_ENV_VAR_MISSING = "RC_CONFIG_PROFILE_ENV_VAR_MISSING"

_PROFILES_RELATIVE_PATH = Path("connections") / "profiles.yml"
_ENV_VAR_PATTERN = re.compile(
    r"""\{\{\s*env_var\(\s*(['"])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\1\s*"""
    r"""(?:,\s*(['"])(?P<default>.*?)\3\s*)?\)\s*\}\}"""
)
_BARE_ENV_VAR_PATTERN = re.compile(
    r"""env_var\(\s*(['"])(?P<name>[A-Za-z_][A-Za-z0-9_]*)\1\s*"""
    r"""(?:,\s*(['"])(?P<default>.*?)\3\s*)?\)"""
)
_ENV_VAR_CALL_PATTERN = re.compile(r"\benv_var\s*\(")
_TEMPLATE_MARKERS = ("{{", "}}", "{%", "%}", "{#", "#}")


class _UniqueKeySafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    """YAML safe loader that rejects duplicate mapping keys."""


def load_selected_profile(
    context: ProjectContext,
    *,
    contracts: tuple[AuthoredContract, ...],
    environ: Mapping[str, str] | None = None,
) -> ProfileLoadResult:
    """Load the selected profile target and referenced connection configs."""
    profile_file = context.project_root / _PROFILES_RELATIVE_PATH
    display_path = _PROFILES_RELATIVE_PATH.as_posix()
    selected_profile_name = context.config.profile

    if selected_profile_name is None:
        return ProfileLoadResult(
            diagnostics=(
                _diagnostic(
                    PROFILE_NOT_SELECTED,
                    "Adapter-aware SQL rendering requires `profile` in recon_project.yml.",
                    path=str(context.project_file),
                    resource_type="project_config",
                    hint="Add `profile: <name>` to recon_project.yml.",
                ),
            )
        )

    if not profile_file.is_file():
        return ProfileLoadResult(
            diagnostics=(
                _diagnostic(
                    PROFILE_FILE_NOT_FOUND,
                    f"Profile file not found: {display_path}.",
                    path=display_path,
                    resource_type="profile_file",
                    hint="Create connections/profiles.yml for adapter-aware SQL rendering.",
                ),
            )
        )

    load_result = _load_profile_yaml(profile_file, display_path)
    if load_result.diagnostics:
        return ProfileLoadResult(diagnostics=load_result.diagnostics)

    raw_profiles = _profiles_mapping(load_result.data, display_path)
    if isinstance(raw_profiles, ProfileLoadResult):
        return raw_profiles

    raw_profile = raw_profiles.get(selected_profile_name)
    if not isinstance(raw_profile, Mapping):
        return ProfileLoadResult(
            diagnostics=(
                _diagnostic(
                    PROFILE_NOT_FOUND,
                    f"Selected profile `{selected_profile_name}` was not found.",
                    path=display_path,
                    resource_type="profile",
                    resource_name=selected_profile_name,
                    hint=(
                        "Add the profile under `profiles` or update `profile` in recon_project.yml."
                    ),
                ),
            )
        )

    raw_target_name = raw_profile.get("target")
    if not isinstance(raw_target_name, str) or raw_target_name == "":
        return _invalid_profile_result(
            display_path,
            "Selected profile must define a non-empty string `target`.",
            resource_name=selected_profile_name,
        )

    raw_outputs = raw_profile.get("outputs")
    if not isinstance(raw_outputs, Mapping):
        return _invalid_profile_result(
            display_path,
            "Selected profile must define an `outputs` mapping.",
            resource_name=selected_profile_name,
        )

    raw_target = raw_outputs.get(raw_target_name)
    if not isinstance(raw_target, Mapping):
        return ProfileLoadResult(
            diagnostics=(
                _diagnostic(
                    PROFILE_TARGET_NOT_FOUND,
                    (
                        f"Selected target `{raw_target_name}` was not found for "
                        f"profile `{selected_profile_name}`."
                    ),
                    path=display_path,
                    resource_type="profile_target",
                    resource_name=selected_profile_name,
                    hint="Add the target under `outputs` or update the profile `target`.",
                ),
            )
        )

    raw_connections = raw_target.get("connections")
    if not isinstance(raw_connections, Mapping):
        return _invalid_profile_result(
            display_path,
            "Selected profile target must define a `connections` mapping.",
            resource_name=selected_profile_name,
        )

    rendered_connections, diagnostics = _referenced_connections(
        raw_connections,
        referenced_connection_names=referenced_connection_names(contracts),
        profile_name=selected_profile_name,
        target_name=raw_target_name,
        profile_path=display_path,
        environ=os.environ if environ is None else environ,
    )
    if diagnostics:
        return ProfileLoadResult(diagnostics=tuple(diagnostics))

    return ProfileLoadResult(
        profile=SelectedProfile(
            name=selected_profile_name,
            target_name=raw_target_name,
            connections=rendered_connections,
        )
    )


def referenced_connection_names(contracts: tuple[AuthoredContract, ...]) -> tuple[str, ...]:
    """Return connection names referenced by selected contracts."""
    names: set[str] = set()
    for contract in contracts:
        names.add(contract.source.connection)
        names.add(contract.target.connection)
    return tuple(sorted(names))


class _YamlLoadResult:
    def __init__(
        self,
        *,
        data: object | None = None,
        diagnostics: tuple[Diagnostic, ...] = (),
    ) -> None:
        self.data = data
        self.diagnostics = diagnostics


def _load_profile_yaml(profile_file: Path, display_path: str) -> _YamlLoadResult:
    try:
        raw_content = profile_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return _YamlLoadResult(
            diagnostics=(
                _diagnostic(
                    INVALID_PROFILE_CONFIG,
                    f"Could not read profile file: {display_path}. Error: {error}",
                    path=display_path,
                    resource_type="profile_file",
                    hint="Check that connections/profiles.yml is readable.",
                ),
            )
        )

    try:
        data: object = yaml.load(raw_content, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        line = mark.line + 1 if mark is not None else None
        column = mark.column + 1 if mark is not None else None
        return _YamlLoadResult(
            diagnostics=(
                _diagnostic(
                    INVALID_PROFILE_YAML,
                    "Invalid YAML in profile file.",
                    path=display_path,
                    resource_type="profile_file",
                    line=line,
                    column=column,
                    hint="Fix the YAML syntax in connections/profiles.yml.",
                ),
            )
        )

    return _YamlLoadResult(data=data)


def _profiles_mapping(
    data: object | None,
    display_path: str,
) -> Mapping[object, object] | ProfileLoadResult:
    if not isinstance(data, Mapping):
        return _invalid_profile_result(
            display_path,
            "Profile file must contain a top-level mapping.",
        )

    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, Mapping):
        return _invalid_profile_result(
            display_path,
            "Profile file must define a `profiles` mapping.",
        )

    return raw_profiles


def _referenced_connections(
    raw_connections: Mapping[object, object],
    *,
    referenced_connection_names: tuple[str, ...],
    profile_name: str,
    target_name: str,
    profile_path: str,
    environ: Mapping[str, str],
) -> tuple[dict[str, ConnectionConfig], list[Diagnostic]]:
    rendered_connections: dict[str, ConnectionConfig] = {}
    diagnostics: list[Diagnostic] = []

    for connection_name in referenced_connection_names:
        raw_connection = raw_connections.get(connection_name)
        if not isinstance(raw_connection, Mapping):
            diagnostics.append(
                _diagnostic(
                    PROFILE_CONNECTION_NOT_FOUND,
                    (
                        f"Connection `{connection_name}` referenced by selected contracts "
                        f"was not found in profile `{profile_name}` target `{target_name}`."
                    ),
                    path=profile_path,
                    resource_type="profile_connection",
                    resource_name=connection_name,
                    hint="Add the named connection or update the contract endpoint connection.",
                )
            )
            continue

        raw_connection_type = raw_connection.get("type")
        if not isinstance(raw_connection_type, str) or raw_connection_type == "":
            diagnostics.append(
                _diagnostic(
                    INVALID_PROFILE_CONFIG,
                    f"Connection `{connection_name}` must define a non-empty string `type`.",
                    path=profile_path,
                    resource_type="profile_connection",
                    resource_name=connection_name,
                    hint="Set the adapter type for this connection.",
                )
            )
            continue
        if _connection_type_uses_template(raw_connection_type):
            diagnostics.append(
                _diagnostic(
                    INVALID_PROFILE_CONFIG,
                    f"Connection `{connection_name}` field `type` must be a literal adapter type.",
                    path=profile_path,
                    resource_type="profile_connection",
                    resource_name=connection_name,
                    hint=(
                        "Set `type` to a literal adapter type such as `duckdb`; use "
                        "`env_var(...)` only for non-routing connection config values."
                    ),
                )
            )
            continue

        rendered_config = _render_value(
            dict(raw_connection),
            connection_name=connection_name,
            profile_path=profile_path,
            environ=environ,
            diagnostics=diagnostics,
        )
        if isinstance(rendered_config, dict):
            connection_type = rendered_config.get("type")
            if not isinstance(connection_type, str) or connection_type == "":
                diagnostics.append(
                    _diagnostic(
                        INVALID_PROFILE_CONFIG,
                        f"Connection `{connection_name}` must define a non-empty string `type`.",
                        path=profile_path,
                        resource_type="profile_connection",
                        resource_name=connection_name,
                        hint="Set the adapter type for this connection.",
                    )
                )
                continue
            rendered_connections[connection_name] = ConnectionConfig(
                name=connection_name,
                type=connection_type,
                config=rendered_config,
            )

    return rendered_connections, diagnostics


def _connection_type_uses_template(value: str) -> bool:
    return _contains_template_marker(value) or re.search(r"\benv_var\s*\(", value) is not None


def _render_value(
    value: object,
    *,
    connection_name: str,
    profile_path: str,
    environ: Mapping[str, str],
    diagnostics: list[Diagnostic],
) -> Any:
    if isinstance(value, str):
        return _render_string(
            value,
            connection_name=connection_name,
            profile_path=profile_path,
            environ=environ,
            diagnostics=diagnostics,
        )
    if isinstance(value, Mapping):
        return {
            key: _render_value(
                nested_value,
                connection_name=connection_name,
                profile_path=profile_path,
                environ=environ,
                diagnostics=diagnostics,
            )
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [
            _render_value(
                item,
                connection_name=connection_name,
                profile_path=profile_path,
                environ=environ,
                diagnostics=diagnostics,
            )
            for item in value
        ]
    return value


def _render_string(
    value: str,
    *,
    connection_name: str,
    profile_path: str,
    environ: Mapping[str, str],
    diagnostics: list[Diagnostic],
) -> str:
    if (
        _contains_unsupported_template_expression(value)
        or _contains_unsupported_env_var_expression(value)
        or _contains_unsupported_env_var_default(value)
    ):
        diagnostics.append(
            _diagnostic(
                INVALID_PROFILE_CONFIG,
                f"Connection `{connection_name}` contains unsupported profile template syntax.",
                path=profile_path,
                resource_type="profile_connection",
                resource_name=connection_name,
                hint=(
                    "Use only env_var('NAME') or env_var('NAME', 'default') in "
                    "connections/profiles.yml."
                ),
            )
        )
        return value

    def replace(match: re.Match[str]) -> str:
        env_name = match.group("name")
        default = match.group("default")
        if env_name in environ:
            return environ[env_name]
        if default is not None:
            return default

        diagnostics.append(
            _diagnostic(
                PROFILE_ENV_VAR_MISSING,
                (
                    f"Connection `{connection_name}` references missing environment "
                    f"variable `{env_name}`."
                ),
                path=profile_path,
                resource_type="profile_connection",
                resource_name=connection_name,
                hint="Set the environment variable or provide an env_var default.",
            )
        )
        return ""

    rendered_value = _ENV_VAR_PATTERN.sub(replace, value)
    bare_match = _BARE_ENV_VAR_PATTERN.fullmatch(value.strip())
    if bare_match is not None:
        return replace(bare_match)
    return rendered_value


def _contains_unsupported_template_expression(value: str) -> bool:
    if not _contains_template_marker(value):
        return False

    valid_spans = tuple(match.span() for match in _ENV_VAR_PATTERN.finditer(value))
    marker_positions = tuple(
        position
        for marker in _TEMPLATE_MARKERS
        for position in _template_marker_positions(value, marker)
    )
    return any(not _position_in_spans(position, valid_spans) for position in marker_positions)


def _contains_template_marker(value: str) -> bool:
    return any(marker in value for marker in _TEMPLATE_MARKERS)


def _contains_unsupported_env_var_expression(value: str) -> bool:
    call_positions = tuple(match.start() for match in _ENV_VAR_CALL_PATTERN.finditer(value))
    if not call_positions:
        return False

    valid_template_spans = tuple(match.span() for match in _ENV_VAR_PATTERN.finditer(value))
    if any(_position_in_spans(position, valid_template_spans) for position in call_positions):
        return any(
            not _position_in_spans(position, valid_template_spans) for position in call_positions
        )

    return _BARE_ENV_VAR_PATTERN.fullmatch(value.strip()) is None


def _contains_unsupported_env_var_default(value: str) -> bool:
    if any(
        _contains_unsupported_env_var_default_value(match.group("default"))
        for match in _ENV_VAR_PATTERN.finditer(value)
    ):
        return True

    bare_match = _BARE_ENV_VAR_PATTERN.fullmatch(value.strip())
    return bare_match is not None and _contains_unsupported_env_var_default_value(
        bare_match.group("default")
    )


def _contains_unsupported_env_var_default_value(default: str | None) -> bool:
    if default is None:
        return False
    return _contains_template_marker(default) or _ENV_VAR_CALL_PATTERN.search(default) is not None


def _template_marker_positions(value: str, marker: str) -> tuple[int, ...]:
    positions: list[int] = []
    start = 0
    while True:
        position = value.find(marker, start)
        if position == -1:
            return tuple(positions)
        positions.append(position)
        start = position + len(marker)


def _position_in_spans(position: int, spans: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= position < end for start, end in spans)


def _construct_mapping_without_duplicate_keys(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
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


def _invalid_profile_result(
    path: str,
    message: str,
    *,
    resource_name: str | None = None,
) -> ProfileLoadResult:
    return ProfileLoadResult(
        diagnostics=(
            _diagnostic(
                INVALID_PROFILE_CONFIG,
                message,
                path=path,
                resource_type="profile",
                resource_name=resource_name,
                hint="Use the documented connections/profiles.yml structure.",
            ),
        )
    )


def _diagnostic(
    code: str,
    message: str,
    *,
    path: str,
    resource_type: str,
    resource_name: str | None = None,
    line: int | None = None,
    column: int | None = None,
    hint: str | None = None,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type=resource_type,
        resource_name=resource_name,
        path=path,
        line=line,
        column=column,
        hint=hint,
    )
