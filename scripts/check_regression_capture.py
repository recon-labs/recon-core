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


def _strip_param_suffix(node_part: str) -> str:
    return node_part.split("[", 1)[0]


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
    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue
        if not _pytest_mark_regression_capture(decorator.func):
            continue
        for arg in decorator.args:
            if isinstance(arg, ast.Constant) and arg.value == row_id:
                return True
        for keyword in decorator.keywords:
            if (
                keyword.arg == "id"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == row_id
            ):
                return True
    return False


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


def _validate_capture_row(
    row: Any,
    *,
    file_path: Path,
    file_area: str,
    repo_root: Path,
    seen_ids: dict[str, Path],
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
    else:
        known_gates = {gate for gate in gates if isinstance(gate, str) and gate}

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
                known_gates=known_gates,
                allowed_statuses=allowed_statuses,
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
