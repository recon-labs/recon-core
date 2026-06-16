from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def load_script() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "check_regression_capture_decisions.py"
    )
    spec = importlib.util.spec_from_file_location("check_regression_capture_decisions", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_capture_project(tmp_path: Path, capture_body: str) -> Path:
    capture_root = tmp_path / "docs" / "compatibility" / "regression-capture"
    capture_root.mkdir(parents=True)
    (capture_root / "index.yml").write_text(
        """
schema_version: 1
allowed_statuses:
  - pending
  - covered
  - migrated
  - deferred
  - not_applicable
capture_files:
  - path: adapter-runtime.yml
    area: adapter-runtime
    description: Adapter runtime captures.
gates:
  adapter_testkit_regression_carryover:
    primary_milestone: adapter_test_kit_and_package_split
    primary_milestone_title: Adapter test kit and adapter package split
    applies_to:
      - adapter test kit implementation
    trigger_surfaces:
      - adapter_runtime
      - adapter_api
      - adapter_capabilities
      - sql_rendering
      - scan_safety
""".lstrip()
    )
    (capture_root / "adapter-runtime.yml").write_text(capture_body)
    return capture_root


def test_advisory_reports_changed_surface_without_capture_or_rationale(tmp_path: Path) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures: []
""".lstrip(),
    )

    findings = script.evaluate(
        changed_paths=["src/recon_core/services/run.py"],
        capture_root=capture_root,
        repo_root=tmp_path,
    )

    assert len(findings) == 1
    assert findings[0].gate == "adapter_testkit_regression_carryover"
    assert findings[0].surfaces == ("adapter_runtime", "scan_safety")


def test_advisory_accepts_existing_capture_row_for_matching_surface(tmp_path: Path) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures:
  - id: existing-scan-safety-row
    title: Existing row
    area: adapter-runtime
    bug_class: scan_safety
    owner_surface: core_runtime_policy
    severity: P2
    current_tests:
      - tests/sample/test_example.py::test_existing_case
    carryover_gates:
      - gate: adapter_testkit_regression_carryover
        status: pending
""".lstrip(),
    )

    findings = script.evaluate(
        changed_paths=["src/recon_core/services/run.py"],
        capture_root=capture_root,
        repo_root=tmp_path,
    )

    assert findings == []


@pytest.mark.regression_capture("regression-capture-decision-advisory-partial-surface-coverage")
def test_advisory_reports_uncovered_surfaces_when_same_gate_has_existing_capture(
    tmp_path: Path,
) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures:
  - id: existing-scan-safety-row
    title: Existing row
    area: adapter-runtime
    bug_class: scan_safety
    owner_surface: core_runtime_policy
    severity: P2
    current_tests:
      - tests/sample/test_example.py::test_existing_case
    carryover_gates:
      - gate: adapter_testkit_regression_carryover
        status: pending
""".lstrip(),
    )

    findings = script.evaluate(
        changed_paths=[
            "src/recon_core/services/run.py",
            "src/recon_core/adapters/duckdb/adapter.py",
        ],
        capture_root=capture_root,
        repo_root=tmp_path,
    )

    assert len(findings) == 1
    assert findings[0].gate == "adapter_testkit_regression_carryover"
    assert findings[0].surfaces == ("adapter_api", "adapter_capabilities", "sql_rendering")
    assert findings[0].paths == ("src/recon_core/adapters/duckdb/adapter.py",)


def test_advisory_accepts_capture_not_required_decision_file(tmp_path: Path) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures: []
""".lstrip(),
    )
    decision_file = tmp_path / "capture-decisions.yml"
    decision_file.write_text(
        """
capture_not_required:
  - id: docs-only-scan-wording
    gates:
      - adapter_testkit_regression_carryover
    surfaces:
      - adapter_runtime
      - scan_safety
    rationale: Documentation wording only; existing capture row already covers behavior.
""".lstrip()
    )

    findings = script.evaluate(
        changed_paths=["src/recon_core/services/run.py"],
        capture_root=capture_root,
        repo_root=tmp_path,
        decision_file=decision_file,
    )

    assert findings == []


def test_main_is_advisory_by_default(tmp_path: Path, capsys) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures: []
""".lstrip(),
    )

    result = script.main(
        [
            "--capture-root",
            str(capture_root),
            "--repo-root",
            str(tmp_path),
            "src/recon_core/services/run.py",
        ]
    )

    assert result == 0
    assert "advisory found potential missing decisions" in capsys.readouterr().out


def test_main_can_fail_on_findings(tmp_path: Path) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures: []
""".lstrip(),
    )

    result = script.main(
        [
            "--capture-root",
            str(capture_root),
            "--repo-root",
            str(tmp_path),
            "--fail-on-findings",
            "src/recon_core/services/run.py",
        ]
    )

    assert result == 1
