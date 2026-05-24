"""YAML serialization helpers for generated artifacts."""

from typing import Any, cast

import yaml


class _IndentedSafeDumper(yaml.SafeDumper):  # type: ignore[misc]
    """Safe dumper that indents nested block lists for readable artifacts."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


def dump_artifact_yaml(payload: object) -> str:
    """Serialize an artifact payload as readable YAML."""
    return cast(str, yaml.dump(payload, Dumper=_IndentedSafeDumper, sort_keys=False))
