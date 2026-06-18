"""Shared YAML loading helpers."""

from typing import Any

import yaml


class _UniqueKeySafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    """YAML safe loader that rejects duplicate mapping keys."""


def load_yaml_with_unique_keys(content: str) -> object:
    """Load YAML text with duplicate-key protection."""
    return yaml.load(content, Loader=_UniqueKeySafeLoader)


def yaml_error_position(error: yaml.YAMLError) -> tuple[int | None, int | None]:
    """Return 1-based YAML error line and column when available."""
    mark = getattr(error, "problem_mark", None)
    if mark is None:
        return None, None
    return mark.line + 1, mark.column + 1


def safe_yaml_error_message(prefix: str, error: yaml.YAMLError) -> str:
    """Return a safe YAML diagnostic message without authored snippets."""
    problem = getattr(error, "problem", None)
    if isinstance(problem, str):
        if problem.startswith("Duplicate YAML key:"):
            return f"{prefix}: duplicate YAML key."
        if problem.startswith("Unsupported YAML mapping key:"):
            return f"{prefix}: unsupported YAML mapping key."
    return f"{prefix}."


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
