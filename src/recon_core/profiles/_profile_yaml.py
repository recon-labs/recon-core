"""Profile YAML file loading."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from recon_core._yaml import load_yaml_with_unique_keys, yaml_error_position
from recon_core.diagnostics import Diagnostic
from recon_core.profiles._diagnostics import (
    INVALID_PROFILE_CONFIG,
    INVALID_PROFILE_YAML,
    invalid_profile_result,
    profile_diagnostic,
)
from recon_core.profiles.models import ProfileLoadResult


@dataclass(frozen=True, slots=True)
class ProfileYamlLoadResult:
    data: object | None = None
    diagnostics: tuple[Diagnostic, ...] = ()


def load_profile_yaml(profile_file: Path, display_path: str) -> ProfileYamlLoadResult:
    try:
        raw_content = profile_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return ProfileYamlLoadResult(
            diagnostics=(
                profile_diagnostic(
                    INVALID_PROFILE_CONFIG,
                    f"Could not read profile file: {display_path}. Error: {error}",
                    path=display_path,
                    resource_type="profile_file",
                    hint="Check that connections/profiles.yml is readable.",
                ),
            )
        )

    try:
        data = load_yaml_with_unique_keys(raw_content)
    except yaml.YAMLError as error:
        line, column = yaml_error_position(error)
        return ProfileYamlLoadResult(
            diagnostics=(
                profile_diagnostic(
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

    return ProfileYamlLoadResult(data=data)


def profiles_mapping(
    data: object | None,
    display_path: str,
) -> Mapping[object, object] | ProfileLoadResult:
    if not isinstance(data, Mapping):
        return invalid_profile_result(
            display_path,
            "Profile file must contain a top-level mapping.",
        )

    raw_profiles = data.get("profiles")
    if not isinstance(raw_profiles, Mapping):
        return invalid_profile_result(
            display_path,
            "Profile file must define a `profiles` mapping.",
        )

    return raw_profiles
