from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Any

import yaml

REQUIRED_CAPTURE_FIELDS = {
    "id",
    "title",
    "area",
    "bug_class",
    "owner_surface",
    "severity",
    "current_tests",
    "carryover_gates",
}


def _load_yaml(path: Path, errors: list[str]) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid YAML: {exc}")
    except OSError as exc:
        errors.append(f"{path}: cannot read file: {exc}")
    return None


def _as_mapping(value: Any, path: Path, errors: list[str]) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    errors.append(f"{path}: expected YAML mapping")
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _normalize_surface(value: str) -> str:
    return value.replace("-", "_")


def _strip_param_suffix(node_part: str) -> str:
    return node_part.split("[", 1)[0]


def _normalize_pytest_nodeid(nodeid: str) -> str | None:
    path_text, separator, node_text = nodeid.partition("::")
    if not separator or not node_text:
        return None
    node_parts = [_strip_param_suffix(part) for part in node_text.split("::") if part]
    if not node_parts:
        return None
    return "::".join([path_text, *node_parts])


def _class_method_node(
    class_node: ast.ClassDef,
    method_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for child in class_node.body:
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name == method_name:
            return child
    return None


def _pytest_mark_regression_capture(func: ast.expr) -> bool:
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "regression_capture"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "mark"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "pytest"
    )


def _decorators_include_regression_capture(
    decorators: list[ast.expr],
    row_id: str,
) -> bool:
    return row_id in _regression_capture_ids_from_decorators(decorators)


def _regression_capture_ids_from_decorators(decorators: list[ast.expr]) -> list[str]:
    marker_ids: list[str] = []
    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue
        if not _pytest_mark_regression_capture(decorator.func):
            continue
        for arg in decorator.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                marker_ids.append(arg.value)
        for keyword in decorator.keywords:
            if (
                keyword.arg == "id"
                and isinstance(keyword.value, ast.Constant)
                and isinstance(keyword.value.value, str)
            ):
                marker_ids.append(keyword.value.value)
    return marker_ids


def _pytest_node_exists(test_file: Path, node_parts: list[str]) -> bool:
    try:
        module = ast.parse(test_file.read_text())
    except (OSError, SyntaxError):
        return False

    if len(node_parts) == 1:
        function_name = _strip_param_suffix(node_parts[0])
        return any(
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == function_name
            for node in module.body
        )

    if len(node_parts) == 2:
        class_name = _strip_param_suffix(node_parts[0])
        method_name = _strip_param_suffix(node_parts[1])
        for node in module.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return _class_method_node(node, method_name) is not None

    return False


def _pytest_node_has_regression_capture_marker(
    test_file: Path,
    node_parts: list[str],
    row_id: str,
) -> bool:
    try:
        module = ast.parse(test_file.read_text())
    except (OSError, SyntaxError):
        return False

    if len(node_parts) == 1:
        function_name = _strip_param_suffix(node_parts[0])
        for node in module.body:
            if (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == function_name
            ):
                return _decorators_include_regression_capture(node.decorator_list, row_id)
        return False

    if len(node_parts) == 2:
        class_name = _strip_param_suffix(node_parts[0])
        method_name = _strip_param_suffix(node_parts[1])
        for node in module.body:
            if not isinstance(node, ast.ClassDef) or node.name != class_name:
                continue
            method_node = _class_method_node(node, method_name)
            if method_node is None:
                return False
            return _decorators_include_regression_capture(
                node.decorator_list + method_node.decorator_list,
                row_id,
            )

    return False


def _validate_current_test(
    nodeid: str,
    row_id: str,
    repo_root: Path,
    row_context: str,
    errors: list[str],
) -> None:
    path_text, separator, node_text = nodeid.partition("::")
    if not separator or not node_text:
        errors.append(f"{row_context}: current_tests entry must be a pytest node id: {nodeid}")
        return

    test_file = repo_root / path_text
    if not test_file.is_file():
        errors.append(f"{row_context}: test file does not exist for {nodeid}")
        return

    node_parts = [part for part in node_text.split("::") if part]
    if not _pytest_node_exists(test_file, node_parts):
        errors.append(f"{row_context}: pytest node not found for {nodeid}")
        return

    if not _pytest_node_has_regression_capture_marker(test_file, node_parts, row_id):
        errors.append(
            f"{row_context}: {nodeid} missing @pytest.mark.regression_capture({row_id!r})"
        )


def _relative_pytest_nodeid(repo_root: Path, test_file: Path, *node_parts: str) -> str:
    if test_file.is_relative_to(repo_root):
        path_text = str(test_file.relative_to(repo_root))
    else:
        path_text = str(test_file)
    return "::".join([path_text, *node_parts])


def _collect_regression_capture_marker_nodeids(repo_root: Path) -> dict[str, set[str]]:
    tests_root = repo_root / "tests"
    marker_nodeids: dict[str, set[str]] = {}
    if not tests_root.is_dir():
        return marker_nodeids

    for test_file in sorted(tests_root.rglob("*.py")):
        try:
            module = ast.parse(test_file.read_text())
        except (OSError, SyntaxError):
            continue

        for node in module.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                nodeid = _relative_pytest_nodeid(repo_root, test_file, node.name)
                for marker_id in _regression_capture_ids_from_decorators(node.decorator_list):
                    marker_nodeids.setdefault(marker_id, set()).add(nodeid)
            if isinstance(node, ast.ClassDef):
                class_marker_ids = _regression_capture_ids_from_decorators(node.decorator_list)
                for child in node.body:
                    if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                        nodeid = _relative_pytest_nodeid(
                            repo_root, test_file, node.name, child.name
                        )
                        for marker_id in class_marker_ids:
                            marker_nodeids.setdefault(marker_id, set()).add(nodeid)
                        for marker_id in _regression_capture_ids_from_decorators(
                            child.decorator_list
                        ):
                            marker_nodeids.setdefault(marker_id, set()).add(nodeid)

    return marker_nodeids


def _validate_regression_capture_markers_have_rows(
    *,
    repo_root: Path,
    seen_ids: dict[str, Path],
    captured_nodeids_by_id: dict[str, set[str]],
    errors: list[str],
) -> None:
    for marker_id, nodeids in sorted(_collect_regression_capture_marker_nodeids(repo_root).items()):
        if marker_id not in seen_ids:
            locations = ", ".join(sorted(nodeids))
            errors.append(
                f"{locations}: orphan regression_capture marker {marker_id!r} "
                "has no matching capture row"
            )
            continue
        captured_nodeids = captured_nodeids_by_id.get(marker_id, set())
        for nodeid in sorted(nodeids - captured_nodeids):
            errors.append(
                f"{nodeid}: regression_capture marker {marker_id!r} is not listed in current_tests"
            )


def _validate_gate_entry(
    gate_entry: Any,
    *,
    row_context: str,
    known_gates: set[str],
    allowed_statuses: set[str],
    errors: list[str],
) -> None:
    if not isinstance(gate_entry, dict):
        errors.append(f"{row_context}: carryover_gates entries must be mappings")
        return

    gate = gate_entry.get("gate")
    if not isinstance(gate, str) or not gate:
        errors.append(f"{row_context}: carryover gate entry missing string 'gate'")
    elif gate not in known_gates:
        errors.append(f"{row_context}: unknown carryover gate '{gate}'")

    status = gate_entry.get("status")
    if not isinstance(status, str) or not status:
        errors.append(f"{row_context}: carryover gate entry missing string 'status'")
        return
    if status not in allowed_statuses:
        errors.append(f"{row_context}: invalid status '{status}'")
        return

    if status in {"deferred", "not_applicable"}:
        rationale = gate_entry.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            errors.append(f"{row_context}: status '{status}' requires rationale")

    if status == "migrated":
        migrated_tests = _string_list(gate_entry.get("migrated_tests"))
        if not migrated_tests:
            errors.append(f"{row_context}: status 'migrated' requires migrated_tests")


def _validate_path_surface_routing(
    index_data: dict[str, Any],
    *,
    index_path: Path,
    known_trigger_surfaces: set[str],
    errors: list[str],
) -> None:
    routing_data = index_data.get("path_surface_routing")
    if not isinstance(routing_data, dict):
        errors.append(f"{index_path}: path_surface_routing must be a mapping")
        return

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
                _normalize_surface(surface) for surface in _string_list(entry.get("surfaces"))
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


def _validate_capture_row(
    row: Any,
    *,
    file_path: Path,
    file_area: str,
    repo_root: Path,
    seen_ids: dict[str, Path],
    captured_nodeids_by_id: dict[str, set[str]],
    known_gates: set[str],
    allowed_statuses: set[str],
    errors: list[str],
) -> None:
    if not isinstance(row, dict):
        errors.append(f"{file_path}: captures entries must be mappings")
        return

    row_id = row.get("id")
    row_context = f"{file_path}: capture {row_id!r}"
    for field in sorted(REQUIRED_CAPTURE_FIELDS):
        if field not in row:
            errors.append(f"{row_context}: missing required field '{field}'")

    if not isinstance(row_id, str) or not row_id:
        errors.append(f"{file_path}: capture row has missing or invalid id")
    elif row_id in seen_ids:
        errors.append(
            f"{file_path}: duplicate capture id '{row_id}' also appears in {seen_ids[row_id]}"
        )
    else:
        seen_ids[row_id] = file_path

    row_area = row.get("area")
    if not isinstance(row_area, str) or row_area != file_area:
        errors.append(f"{row_context}: area must match file area '{file_area}'")

    current_tests = _string_list(row.get("current_tests"))
    if not current_tests:
        errors.append(f"{row_context}: current_tests must be a non-empty list of pytest nodes")
    for nodeid in current_tests:
        if isinstance(row_id, str):
            normalized_nodeid = _normalize_pytest_nodeid(nodeid)
            if normalized_nodeid is not None:
                captured_nodeids_by_id.setdefault(row_id, set()).add(normalized_nodeid)
            _validate_current_test(nodeid, row_id, repo_root, row_context, errors)

    carryover_gates = row.get("carryover_gates")
    if not isinstance(carryover_gates, list) or not carryover_gates:
        errors.append(f"{row_context}: carryover_gates must be a non-empty list")
        return
    for gate_entry in carryover_gates:
        _validate_gate_entry(
            gate_entry,
            row_context=row_context,
            known_gates=known_gates,
            allowed_statuses=allowed_statuses,
            errors=errors,
        )


def validate(
    *,
    capture_root: Path | None = None,
    repo_root: Path | None = None,
) -> list[str]:
    script_root = Path(__file__).resolve().parents[1]
    repo_root = repo_root or script_root
    capture_root = capture_root or repo_root / "docs" / "compatibility" / "regression-capture"
    errors: list[str] = []

    index_path = capture_root / "index.yml"
    index_data = _as_mapping(_load_yaml(index_path, errors), index_path, errors)
    if index_data is None:
        return errors

    allowed_statuses = set(_string_list(index_data.get("allowed_statuses")))
    if not allowed_statuses:
        errors.append(f"{index_path}: allowed_statuses must be a non-empty list")

    gates = index_data.get("gates")
    if not isinstance(gates, dict) or not gates:
        errors.append(f"{index_path}: gates must be a non-empty mapping")
        known_gates: set[str] = set()
        known_trigger_surfaces: set[str] = set()
    else:
        known_gates = {gate for gate in gates if isinstance(gate, str) and gate}
        known_trigger_surfaces = {
            _normalize_surface(surface)
            for gate_data in gates.values()
            if isinstance(gate_data, dict)
            for surface in _string_list(gate_data.get("trigger_surfaces"))
        }

    _validate_path_surface_routing(
        index_data,
        index_path=index_path,
        known_trigger_surfaces=known_trigger_surfaces,
        errors=errors,
    )

    capture_file_entries = index_data.get("capture_files")
    if not isinstance(capture_file_entries, list) or not capture_file_entries:
        errors.append(f"{index_path}: capture_files must be a non-empty list")
        return errors

    expected_files: dict[str, str] = {}
    for entry in capture_file_entries:
        if not isinstance(entry, dict):
            errors.append(f"{index_path}: capture_files entries must be mappings")
            continue
        path = entry.get("path")
        area = entry.get("area")
        if not isinstance(path, str) or not path.endswith(".yml"):
            errors.append(f"{index_path}: capture file entry has invalid path")
            continue
        if not isinstance(area, str) or not area:
            errors.append(f"{index_path}: capture file entry {path} has invalid area")
            continue
        expected_files[path] = area

    actual_yaml_files = {
        path.name for path in capture_root.glob("*.yml") if path.name != "index.yml"
    }
    for unexpected_file in sorted(actual_yaml_files - set(expected_files)):
        errors.append(f"{capture_root / unexpected_file}: unexpected capture file")

    seen_ids: dict[str, Path] = {}
    captured_nodeids_by_id: dict[str, set[str]] = {}
    for relative_path, expected_area in expected_files.items():
        file_path = capture_root / relative_path
        if not file_path.is_file():
            errors.append(f"{file_path}: expected capture file is missing")
            continue
        file_data = _as_mapping(_load_yaml(file_path, errors), file_path, errors)
        if file_data is None:
            continue

        file_area = file_data.get("area")
        if file_area != expected_area:
            errors.append(f"{file_path}: area must be '{expected_area}'")
            file_area = expected_area

        captures = file_data.get("captures")
        if not isinstance(captures, list):
            errors.append(f"{file_path}: captures must be a list")
            continue
        for row in captures:
            _validate_capture_row(
                row,
                file_path=file_path,
                file_area=expected_area,
                repo_root=repo_root,
                seen_ids=seen_ids,
                captured_nodeids_by_id=captured_nodeids_by_id,
                known_gates=known_gates,
                allowed_statuses=allowed_statuses,
                errors=errors,
            )

    _validate_regression_capture_markers_have_rows(
        repo_root=repo_root,
        seen_ids=seen_ids,
        captured_nodeids_by_id=captured_nodeids_by_id,
        errors=errors,
    )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate regression capture metadata.")
    parser.add_argument(
        "--capture-root",
        type=Path,
        default=None,
        help="Path to docs/compatibility/regression-capture.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root used to resolve current_tests paths.",
    )
    args = parser.parse_args(argv)

    errors = validate(capture_root=args.capture_root, repo_root=args.repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("Regression capture validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
