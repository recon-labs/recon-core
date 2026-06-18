from __future__ import annotations

import importlib.util
from pathlib import Path
from subprocess import CompletedProcess
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
path_surface_routing:
  exact:
    - path: src/recon_core/services/run.py
      surfaces:
        - adapter_runtime
        - scan_safety
    - path: src/recon_core/check_engine/scan_budget.py
      surfaces:
        - scan_safety
    - path: src/recon_core/adapters/runtime_safety.py
      surfaces:
        - adapter_runtime
        - scan_safety
    - path: src/recon_core/adapters/duckdb/runtime_scan_guard.py
      surfaces:
        - adapter_runtime
        - scan_safety
    - path: src/recon_core/adapters/duckdb/adapter.py
      surfaces:
        - adapter_runtime
        - adapter_capabilities
        - sql_rendering
  prefixes:
    - prefix: src/recon_core/adapters/
      surfaces:
        - adapter_api
        - adapter_capabilities
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


@pytest.mark.regression_capture("regression-capture-decision-advisory-scan-budget-surface")
def test_advisory_maps_scan_budget_module_to_scan_safety_surface(tmp_path: Path) -> None:
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
        changed_paths=["src/recon_core/check_engine/scan_budget.py"],
        capture_root=capture_root,
        repo_root=tmp_path,
    )

    assert len(findings) == 1
    assert findings[0].gate == "adapter_testkit_regression_carryover"
    assert findings[0].surfaces == ("scan_safety",)
    assert findings[0].paths == ("src/recon_core/check_engine/scan_budget.py",)


@pytest.mark.regression_capture("regression-capture-decision-advisory-metadata-routing")
@pytest.mark.parametrize(
    "changed_path",
    [
        "src/recon_core/adapters/runtime_safety.py",
        "src/recon_core/adapters/duckdb/runtime_scan_guard.py",
    ],
)
def test_advisory_maps_runtime_safety_modules_to_scan_safety_surface(
    tmp_path: Path,
    changed_path: str,
) -> None:
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
        changed_paths=[changed_path],
        capture_root=capture_root,
        repo_root=tmp_path,
    )

    assert len(findings) == 1
    assert findings[0].gate == "adapter_testkit_regression_carryover"
    assert "scan_safety" in findings[0].surfaces
    assert findings[0].paths == (changed_path,)


@pytest.mark.regression_capture("regression-capture-decision-advisory-metadata-routing")
def test_advisory_uses_path_surface_routing_from_index(tmp_path: Path) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures: []
""".lstrip(),
    )
    index_path = capture_root / "index.yml"
    index_text = index_path.read_text()
    index_path.write_text(
        index_text.replace(
            "  exact:\n",
            """  exact:
    - path: custom/runtime_policy.py
      surfaces:
        - scan_safety
""",
            1,
        )
    )

    findings = script.evaluate(
        changed_paths=["custom/runtime_policy.py"],
        capture_root=capture_root,
        repo_root=tmp_path,
    )

    assert len(findings) == 1
    assert findings[0].gate == "adapter_testkit_regression_carryover"
    assert findings[0].surfaces == ("scan_safety",)
    assert findings[0].paths == ("custom/runtime_policy.py",)


@pytest.mark.regression_capture("regression-capture-decision-advisory-metadata-routing")
def test_advisory_fails_when_path_surface_routing_is_missing(
    tmp_path: Path,
    capsys,
) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures: []
""".lstrip(),
    )
    index_path = capture_root / "index.yml"
    index_path.write_text(
        index_path.read_text().replace(
            "path_surface_routing:",
            "missing_path_surface_routing:",
            1,
        )
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

    captured = capsys.readouterr()
    assert result == 1
    assert "path_surface_routing must be a mapping" in captured.err
    assert "no missing decisions found" not in captured.out


@pytest.mark.regression_capture("regression-capture-decision-advisory-metadata-routing")
def test_advisory_fails_when_path_surface_routing_names_unknown_surface(
    tmp_path: Path,
    capsys,
) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures: []
""".lstrip(),
    )
    index_path = capture_root / "index.yml"
    index_path.write_text(
        index_path.read_text().replace(
            "        - adapter_runtime",
            "        - missing_surface",
            1,
        )
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

    captured = capsys.readouterr()
    assert result == 1
    assert "unknown trigger surface 'missing_surface'" in captured.err
    assert "no missing decisions found" not in captured.out


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


@pytest.mark.regression_capture("regression-capture-decision-advisory-branch-wide-mode")
def test_changed_paths_from_git_includes_branch_diff_when_base_ref_is_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script()
    commands: list[tuple[str, ...]] = []

    def fake_run(
        command: tuple[str, ...],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> CompletedProcess[str]:
        commands.append(command)
        assert check is False
        assert capture_output is True
        assert text is True
        if command[3:] == ("merge-base", "HEAD", "origin/main"):
            return CompletedProcess(command, 0, stdout="abc123\n", stderr="")
        if command[3:] == ("diff", "--name-only", "abc123...HEAD", "--"):
            return CompletedProcess(
                command,
                0,
                stdout="src/recon_core/adapters/duckdb/adapter.py\n",
                stderr="",
            )
        if command[3:] == ("diff", "--name-only", "HEAD", "--"):
            return CompletedProcess(command, 0, stdout="tests/wip.py\n", stderr="")
        if command[3:] == ("ls-files", "--others", "--exclude-standard"):
            return CompletedProcess(command, 0, stdout="tests/new.py\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    paths = script._changed_paths_from_git(tmp_path, base_ref="origin/main")

    assert paths == [
        "src/recon_core/adapters/duckdb/adapter.py",
        "tests/new.py",
        "tests/wip.py",
    ]
    assert commands[0][3:] == ("merge-base", "HEAD", "origin/main")


@pytest.mark.regression_capture("regression-capture-decision-advisory-branch-wide-mode")
def test_main_base_ref_uses_branch_wide_changed_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures: []
""".lstrip(),
    )

    def fake_changed_paths(repo_root: Path, *, base_ref: str | None = None) -> list[str]:
        assert repo_root == tmp_path
        assert base_ref == "origin/main"
        return ["src/recon_core/services/run.py"]

    monkeypatch.setattr(script, "_changed_paths_from_git", fake_changed_paths)

    result = script.main(
        [
            "--capture-root",
            str(capture_root),
            "--repo-root",
            str(tmp_path),
            "--base-ref",
            "origin/main",
        ]
    )

    assert result == 0
    assert "advisory found potential missing decisions" in capsys.readouterr().out


@pytest.mark.regression_capture("regression-capture-decision-advisory-branch-wide-mode")
def test_main_base_ref_fails_when_ref_cannot_be_resolved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    script = load_script()
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures: []
""".lstrip(),
    )

    def fake_run(
        command: tuple[str, ...],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> CompletedProcess[str]:
        assert check is False
        assert capture_output is True
        assert text is True
        if command[3:] == ("merge-base", "HEAD", "origin/main"):
            return CompletedProcess(command, 1, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    result = script.main(
        [
            "--capture-root",
            str(capture_root),
            "--repo-root",
            str(tmp_path),
            "--base-ref",
            "origin/main",
        ]
    )

    assert result == 1
    captured = capsys.readouterr()
    assert "Could not resolve base ref `origin/main`." in captured.err
    assert "no missing decisions found" not in captured.out
