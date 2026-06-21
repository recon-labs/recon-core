"""Profile env-var rendering for referenced connection payloads."""

import re
from collections.abc import Mapping
from typing import Any

from recon_core.diagnostics import Diagnostic
from recon_core.profiles._diagnostics import (
    INVALID_PROFILE_CONFIG,
    PROFILE_ENV_VAR_MISSING,
    profile_diagnostic,
)

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


def connection_type_uses_template(value: str) -> bool:
    return contains_template_marker(value) or re.search(r"\benv_var\s*\(", value) is not None


def render_profile_value(
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
            key: render_profile_value(
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
            render_profile_value(
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
            profile_diagnostic(
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
            profile_diagnostic(
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
    if not contains_template_marker(value):
        return False

    valid_spans = tuple(match.span() for match in _ENV_VAR_PATTERN.finditer(value))
    marker_positions = tuple(
        position
        for marker in _TEMPLATE_MARKERS
        for position in _template_marker_positions(value, marker)
    )
    return any(not _position_in_spans(position, valid_spans) for position in marker_positions)


def contains_template_marker(value: str) -> bool:
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
    return contains_template_marker(default) or _ENV_VAR_CALL_PATTERN.search(default) is not None


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
