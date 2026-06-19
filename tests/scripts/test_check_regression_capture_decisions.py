from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from subprocess import CompletedProcess
from types import ModuleType

import pytest


def load_script() -> ModuleType:
    script_dir = Path(__file__).resolve().parents[2] / "scripts"
    script_path = script_dir / "check_regression_capture_decisions.py"
    spec = importlib.util.spec_from_file_location("check_regression_capture_decisions", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    original_sys_path = list(sys.path)
    sys.path.insert(0, str(script_dir))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path
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
  - path: parser-compiler.yml
    area: parser-compiler
    description: Parser and compiler captures.
  - path: diagnostics-privacy.yml
    area: diagnostics-privacy
    description: Diagnostic privacy captures.
  - path: artifacts.yml
    area: artifacts
    description: Artifact captures.
path_surface_routing:
  exact:
    - path: src/recon_core/_yaml.py
      surfaces:
        - artifact_lifecycle
        - contract_yaml
        - diagnostics
        - generated_artifacts
        - parser
        - profile_secrets
        - redaction
        - source_target_privacy
    - path: src/recon_core/config/project_config.py
      surfaces:
        - diagnostics
        - redaction
    - path: src/recon_core/compiled_artifact_schema.py
      surfaces:
        - artifact_lifecycle
        - generated_artifacts
        - typed_check_plan
    - path: src/recon_core/compiler/models.py
      surfaces:
        - typed_check_plan
    - path: src/recon_core/parser/yaml_loader.py
      surfaces:
        - contract_yaml
        - diagnostics
        - parser
        - redaction
        - source_target_privacy
    - path: src/recon_core/profiles/loader.py
      surfaces:
        - diagnostics
        - profile_secrets
        - redaction
    - path: src/recon_core/profiles/connection_references.py
      surfaces:
        - diagnostics
        - profile_secrets
        - redaction
    - path: scripts/check_regression_capture.py
      surfaces:
        - regression_capture_metadata
    - path: scripts/check_regression_capture_decisions.py
      surfaces:
        - regression_capture_metadata
    - path: scripts/regression_capture_metadata.py
      surfaces:
        - regression_capture_metadata
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
    - path: tests/profiles/test_connection_references.py
      surfaces:
        - diagnostics
        - profile_secrets
        - redaction
  prefixes:
    - prefix: src/recon_core/adapters/
      surfaces:
        - adapter_api
        - adapter_capabilities
    - prefix: docs/compatibility/regression-capture/
      surfaces:
        - regression_capture_metadata
    - prefix: tests/scripts/
      surfaces:
        - regression_capture_metadata
gates:
  artifact_publication_carryover:
    primary_milestone: runner_and_results
    primary_milestone_title: Runner and results
    applies_to:
      - any generated artifact writer or cleanup surface
    trigger_surfaces:
      - artifact_lifecycle
      - generated_artifacts
  diagnostics_privacy_carryover:
    primary_milestone: runner_and_results
    primary_milestone_title: Runner and results
    applies_to:
      - any diagnostic, log, failure-detail, evidence, or debug surface
    trigger_surfaces:
      - diagnostics
      - profile_secrets
      - redaction
      - source_target_privacy
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
  parser_compiler_contract_carryover:
    primary_milestone: aggregate_metrics_expansion
    primary_milestone_title: Aggregate metrics expansion
    applies_to:
      - any YAML schema, validation default, check-pack expansion, or typed-plan change
    trigger_surfaces:
      - contract_yaml
      - parser
      - regression_capture_metadata
      - typed_check_plan
""".lstrip()
    )
    (capture_root / "adapter-runtime.yml").write_text(capture_body)
    (capture_root / "artifacts.yml").write_text(
        "schema_version: 1\narea: artifacts\ncaptures: []\n"
    )
    (capture_root / "diagnostics-privacy.yml").write_text(
        "schema_version: 1\narea: diagnostics-privacy\ncaptures: []\n"
    )
    (capture_root / "parser-compiler.yml").write_text(
        "schema_version: 1\narea: parser-compiler\ncaptures: []\n"
    )
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
@pytest.mark.parametrize(
    ("changed_path", "expected_surfaces_by_gate"),
    [
        (
            "src/recon_core/_yaml.py",
            {
                "artifact_publication_carryover": (
                    "artifact_lifecycle",
                    "generated_artifacts",
                ),
                "diagnostics_privacy_carryover": (
                    "diagnostics",
                    "profile_secrets",
                    "redaction",
                    "source_target_privacy",
                ),
                "parser_compiler_contract_carryover": ("contract_yaml", "parser"),
            },
        ),
        (
            "src/recon_core/config/project_config.py",
            {
                "diagnostics_privacy_carryover": (
                    "diagnostics",
                    "redaction",
                ),
            },
        ),
        (
            "src/recon_core/parser/yaml_loader.py",
            {
                "diagnostics_privacy_carryover": (
                    "diagnostics",
                    "redaction",
                    "source_target_privacy",
                ),
                "parser_compiler_contract_carryover": ("contract_yaml", "parser"),
            },
        ),
        (
            "src/recon_core/profiles/loader.py",
            {
                "diagnostics_privacy_carryover": (
                    "diagnostics",
                    "profile_secrets",
                    "redaction",
                ),
            },
        ),
        (
            "src/recon_core/profiles/connection_references.py",
            {
                "diagnostics_privacy_carryover": (
                    "diagnostics",
                    "profile_secrets",
                    "redaction",
                ),
            },
        ),
        (
            "tests/profiles/test_connection_references.py",
            {
                "diagnostics_privacy_carryover": (
                    "diagnostics",
                    "profile_secrets",
                    "redaction",
                ),
            },
        ),
    ],
)
def test_advisory_maps_yaml_and_profile_modules_to_carryover_surfaces(
    tmp_path: Path,
    changed_path: str,
    expected_surfaces_by_gate: dict[str, tuple[str, ...]],
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

    assert {finding.gate: finding.surfaces for finding in findings} == expected_surfaces_by_gate
    assert {finding.gate: finding.paths for finding in findings} == dict.fromkeys(
        expected_surfaces_by_gate, (changed_path,)
    )


@pytest.mark.regression_capture("regression-capture-decision-advisory-metadata-routing")
@pytest.mark.parametrize(
    ("changed_path", "expected_surfaces_by_gate"),
    [
        (
            "src/recon_core/compiled_artifact_schema.py",
            {
                "artifact_publication_carryover": (
                    "artifact_lifecycle",
                    "generated_artifacts",
                ),
                "parser_compiler_contract_carryover": ("typed_check_plan",),
            },
        ),
        (
            "src/recon_core/compiler/models.py",
            {
                "parser_compiler_contract_carryover": ("typed_check_plan",),
            },
        ),
    ],
)
def test_advisory_maps_compiled_artifact_schema_modules_to_carryover_surfaces(
    tmp_path: Path,
    changed_path: str,
    expected_surfaces_by_gate: dict[str, tuple[str, ...]],
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

    assert {finding.gate: finding.surfaces for finding in findings} == expected_surfaces_by_gate
    assert {finding.gate: finding.paths for finding in findings} == dict.fromkeys(
        expected_surfaces_by_gate, (changed_path,)
    )


@pytest.mark.regression_capture("regression-capture-decision-advisory-metadata-routing")
@pytest.mark.parametrize(
    "changed_path",
    [
        "scripts/check_regression_capture.py",
        "scripts/check_regression_capture_decisions.py",
        "scripts/regression_capture_metadata.py",
        "tests/scripts/test_check_regression_capture.py",
        "tests/scripts/test_check_regression_capture_decisions.py",
    ],
)
def test_advisory_maps_regression_capture_tooling_to_metadata_surface(
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
    assert findings[0].gate == "parser_compiler_contract_carryover"
    assert findings[0].surfaces == ("regression_capture_metadata",)
    assert findings[0].paths == (changed_path,)


@pytest.mark.regression_capture("regression-capture-decision-advisory-metadata-routing")
@pytest.mark.parametrize(
    "changed_path",
    [
        "docs/compatibility/regression-capture/index.yml",
        "docs/compatibility/regression-capture/parser-compiler.yml",
    ],
)
def test_advisory_maps_regression_capture_metadata_files_to_metadata_surface(
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
    assert findings[0].gate == "parser_compiler_contract_carryover"
    assert findings[0].surfaces == ("regression_capture_metadata",)
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
    capsys: pytest.CaptureFixture[str],
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
    capsys: pytest.CaptureFixture[str],
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


def test_main_is_advisory_by_default(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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
    capsys: pytest.CaptureFixture[str],
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
    capsys: pytest.CaptureFixture[str],
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
