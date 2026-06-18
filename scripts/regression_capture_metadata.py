from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple


class RegressionCaptureMetadataError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


class PathSurfaceRouting(NamedTuple):
    exact: dict[str, set[str]]
    prefixes: tuple[tuple[str, set[str]], ...]


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def string_list(value: Any) -> list[str]:
    return [item for item in as_list(value) if isinstance(item, str) and item]


def normalize_surface(value: str) -> str:
    return value.replace("-", "_")


def normalize_path(value: str) -> str:
    return value.replace("\\", "/")


def gate_trigger_surfaces(index_data: dict[str, Any]) -> dict[str, set[str]]:
    gates = index_data.get("gates")
    if not isinstance(gates, dict):
        return {}

    trigger_surfaces: dict[str, set[str]] = {}
    for gate, gate_data in gates.items():
        if not isinstance(gate, str) or not isinstance(gate_data, dict):
            continue
        trigger_surfaces[gate] = {
            normalize_surface(surface) for surface in string_list(gate_data.get("trigger_surfaces"))
        }
    return trigger_surfaces


def validate_path_surface_routing(index_data: dict[str, Any], *, index_path: Path) -> list[str]:
    errors: list[str] = []
    known_trigger_surfaces = {
        surface for surfaces in gate_trigger_surfaces(index_data).values() for surface in surfaces
    }
    routing_data = index_data.get("path_surface_routing")
    if not isinstance(routing_data, dict):
        return [f"{index_path}: path_surface_routing must be a mapping"]

    route_count = 0
    for section, path_field in (("exact", "path"), ("prefixes", "prefix")):
        entries = routing_data.get(section)
        if not isinstance(entries, list):
            errors.append(f"{index_path}: path_surface_routing.{section} must be a list")
            continue
        for index, entry in enumerate(entries):
            route_context = f"{index_path}: path_surface_routing.{section}[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{route_context}: entry must be a mapping")
                continue
            route_path = entry.get(path_field)
            if not isinstance(route_path, str) or not route_path:
                errors.append(f"{route_context}: missing non-empty string '{path_field}'")
            surfaces = {
                normalize_surface(surface) for surface in string_list(entry.get("surfaces"))
            }
            if not surfaces:
                errors.append(f"{route_context}: surfaces must be a non-empty string list")
                continue
            unknown_surfaces = surfaces - known_trigger_surfaces
            for surface in sorted(unknown_surfaces):
                errors.append(f"{route_context}: unknown trigger surface '{surface}'")
            route_count += 1

    if route_count == 0:
        errors.append(f"{index_path}: path_surface_routing must define at least one route")
    return errors


def parse_path_surface_routing(
    index_data: dict[str, Any],
    *,
    index_path: Path,
) -> PathSurfaceRouting:
    errors = validate_path_surface_routing(index_data, index_path=index_path)
    if errors:
        raise RegressionCaptureMetadataError(errors)

    routing_data = index_data["path_surface_routing"]

    exact: dict[str, set[str]] = {}
    for entry in routing_data["exact"]:
        exact[normalize_path(entry["path"])] = {
            normalize_surface(surface) for surface in string_list(entry.get("surfaces"))
        }

    prefixes: list[tuple[str, set[str]]] = []
    for entry in routing_data["prefixes"]:
        prefixes.append(
            (
                normalize_path(entry["prefix"]),
                {normalize_surface(surface) for surface in string_list(entry.get("surfaces"))},
            )
        )

    return PathSurfaceRouting(exact=exact, prefixes=tuple(prefixes))
