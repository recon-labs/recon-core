from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

import yaml


class Finding(NamedTuple):
    gate: str
    surfaces: tuple[str, ...]
    paths: tuple[str, ...]


EXACT_PATH_SURFACES: dict[str, set[str]] = {
    "src/recon_core/services/run.py": {"adapter_runtime", "scan_safety"},
    "tests/services/test_run_service.py": {"adapter_runtime", "scan_safety"},
    "src/recon_core/adapters/duckdb/adapter.py": {
        "adapter_runtime",
        "adapter_capabilities",
        "sql_rendering",
    },
    "tests/adapters/test_duckdb_sql_renderer.py": {"sql_rendering"},
}

PREFIX_PATH_SURFACES: tuple[tuple[str, set[str]], ...] = (
    ("src/recon_core/adapters/", {"adapter_api", "adapter_capabilities"}),
    ("tests/adapters/", {"adapter_api", "adapter_capabilities"}),
    (
        "src/recon_core/check_engine/",
        {"check_engine", "execution_result", "prerequisite_blocking", "typed_check_plan"},
    ),
    (
        "tests/check_engine/",
        {"check_engine", "execution_result", "prerequisite_blocking", "typed_check_plan"},
    ),
    ("src/recon_core/cli/", {"cli", "terminal_output", "exit_codes"}),
    ("tests/cli/", {"cli", "terminal_output", "exit_codes"}),
    ("src/recon_core/artifacts/", {"generated_artifacts", "artifact_lifecycle"}),
    ("tests/artifacts/", {"generated_artifacts", "artifact_lifecycle"}),
    ("src/recon_core/evidence", {"evidence"}),
    ("tests/evidence", {"evidence"}),
)


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [item for item in _as_list(value) if isinstance(item, str) and item]


def _normalize_surface(value: str) -> str:
    return value.replace("-", "_")


def surfaces_for_path(path: str) -> set[str]:
    normalized = path.replace("\\", "/")
    surfaces = set(EXACT_PATH_SURFACES.get(normalized, set()))
    for prefix, prefix_surfaces in PREFIX_PATH_SURFACES:
        if normalized.startswith(prefix):
            surfaces.update(prefix_surfaces)
    return surfaces


def _capture_row_surfaces(row: dict[str, Any]) -> set[str]:
    surfaces: set[str] = set()
    for field in ("area", "bug_class", "owner_surface"):
        value = row.get(field)
        if isinstance(value, str) and value:
            surfaces.add(_normalize_surface(value))
    return surfaces


def _load_index(capture_root: Path) -> dict[str, Any]:
    data = _load_yaml(capture_root / "index.yml")
    return data if isinstance(data, dict) else {}


def _gate_trigger_surfaces(index_data: dict[str, Any]) -> dict[str, set[str]]:
    gates = index_data.get("gates")
    if not isinstance(gates, dict):
        return {}

    trigger_surfaces: dict[str, set[str]] = {}
    for gate, gate_data in gates.items():
        if not isinstance(gate, str) or not isinstance(gate_data, dict):
            continue
        trigger_surfaces[gate] = {
            _normalize_surface(surface)
            for surface in _string_list(gate_data.get("trigger_surfaces"))
        }
    return trigger_surfaces


def _capture_files(index_data: dict[str, Any]) -> list[str]:
    files: list[str] = []
    for entry in _as_list(index_data.get("capture_files")):
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if isinstance(path, str) and path:
            files.append(path)
    return files


def _captured_surfaces_by_gate(
    capture_root: Path,
    index_data: dict[str, Any],
) -> dict[str, set[str]]:
    captured: dict[str, set[str]] = {}
    for capture_file in _capture_files(index_data):
        file_data = _load_yaml(capture_root / capture_file)
        if not isinstance(file_data, dict):
            continue
        for row in _as_list(file_data.get("captures")):
            if not isinstance(row, dict):
                continue
            row_surfaces = _capture_row_surfaces(row)
            for gate_entry in _as_list(row.get("carryover_gates")):
                if not isinstance(gate_entry, dict):
                    continue
                gate = gate_entry.get("gate")
                if isinstance(gate, str) and gate:
                    captured.setdefault(gate, set()).update(row_surfaces)
    return captured


def _capture_not_required_decisions(decision_file: Path | None) -> dict[str, set[str]]:
    if decision_file is None:
        return {}
    data = _load_yaml(decision_file)
    if not isinstance(data, dict):
        return {}

    decisions: dict[str, set[str]] = {}
    for entry in _as_list(data.get("capture_not_required")):
        if not isinstance(entry, dict):
            continue
        rationale = entry.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            continue
        gates = _string_list(entry.get("gates"))
        surfaces = {_normalize_surface(surface) for surface in _string_list(entry.get("surfaces"))}
        for gate in gates:
            decisions.setdefault(gate, set()).update(surfaces)
    return decisions


def _changed_paths_from_git(repo_root: Path) -> list[str]:
    commands = (
        ("git", "-C", str(repo_root), "diff", "--name-only", "HEAD", "--"),
        ("git", "-C", str(repo_root), "ls-files", "--others", "--exclude-standard"),
    )
    paths: list[str] = []
    for command in commands:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            paths.extend(line.strip() for line in result.stdout.splitlines() if line.strip())
    return sorted(set(paths))


def evaluate(
    *,
    changed_paths: list[str],
    capture_root: Path | None = None,
    repo_root: Path | None = None,
    decision_file: Path | None = None,
) -> list[Finding]:
    script_root = Path(__file__).resolve().parents[1]
    repo_root = repo_root or script_root
    capture_root = capture_root or repo_root / "docs" / "compatibility" / "regression-capture"
    index_data = _load_index(capture_root)
    gate_surfaces = _gate_trigger_surfaces(index_data)
    captured_surfaces = _captured_surfaces_by_gate(capture_root, index_data)
    not_required = _capture_not_required_decisions(decision_file)

    matched_surfaces_by_gate: dict[str, set[str]] = {}
    paths_by_gate_surface: dict[str, dict[str, set[str]]] = {}
    for path in changed_paths:
        changed_surfaces = surfaces_for_path(path)
        if not changed_surfaces:
            continue
        for gate, trigger_surfaces in gate_surfaces.items():
            matched_surfaces = changed_surfaces & trigger_surfaces
            if matched_surfaces:
                matched_surfaces_by_gate.setdefault(gate, set()).update(matched_surfaces)
                paths_by_surface = paths_by_gate_surface.setdefault(gate, {})
                for surface in matched_surfaces:
                    paths_by_surface.setdefault(surface, set()).add(path)

    findings: list[Finding] = []
    for gate, surfaces in sorted(matched_surfaces_by_gate.items()):
        covered_surfaces = captured_surfaces.get(gate, set()) | not_required.get(gate, set())
        unresolved_surfaces = surfaces - covered_surfaces
        if not unresolved_surfaces:
            continue
        unresolved_paths: set[str] = set()
        for surface in unresolved_surfaces:
            unresolved_paths.update(paths_by_gate_surface.get(gate, {}).get(surface, set()))
        findings.append(
            Finding(
                gate=gate,
                surfaces=tuple(sorted(unresolved_surfaces)),
                paths=tuple(sorted(unresolved_paths)),
            )
        )
    return findings


def _paths_from_stdin() -> list[str]:
    return [line.strip() for line in sys.stdin if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Advisory check for regression capture decisions on changed paths."
    )
    parser.add_argument("paths", nargs="*", help="Changed paths to inspect.")
    parser.add_argument(
        "--paths-from-stdin",
        action="store_true",
        help="Read changed paths from standard input.",
    )
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
        help="Repository root used to discover changed paths when none are provided.",
    )
    parser.add_argument(
        "--decision-file",
        type=Path,
        default=None,
        help="YAML file containing capture_not_required entries.",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Return exit code 1 when advisory findings are present.",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root or Path(__file__).resolve().parents[1]
    changed_paths = list(args.paths)
    if args.paths_from_stdin:
        changed_paths.extend(_paths_from_stdin())
    if not changed_paths:
        changed_paths = _changed_paths_from_git(repo_root)

    findings = evaluate(
        changed_paths=changed_paths,
        capture_root=args.capture_root,
        repo_root=repo_root,
        decision_file=args.decision_file,
    )
    if findings:
        print("Regression capture decision advisory found potential missing decisions:")
        for finding in findings:
            print(f"- gate: {finding.gate}")
            print(f"  surfaces: {', '.join(finding.surfaces)}")
            print(f"  paths: {', '.join(finding.paths)}")
            print(
                "  action: add/update a capture row or provide a "
                "capture_not_required decision-file rationale and record "
                "regression_capture_decision: not-required."
            )
        return 1 if args.fail_on_findings else 0

    print("Regression capture decision advisory: no missing decisions found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
