from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_script() -> ModuleType:
    script_dir = Path(__file__).resolve().parents[2] / "scripts"
    script_path = script_dir / "check_regression_capture.py"
    spec = importlib.util.spec_from_file_location("check_regression_capture", script_path)
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
path_surface_routing:
  exact:
    - path: src/recon_core/services/run.py
      surfaces:
        - adapter_runtime
  prefixes:
    - prefix: src/recon_core/adapters/
      surfaces:
        - adapter_runtime
gates:
  adapter_testkit_regression_carryover:
    primary_milestone: adapter_test_kit_and_package_split
    primary_milestone_title: Adapter test kit and adapter package split
    applies_to:
      - adapter test kit implementation
    trigger_surfaces:
      - adapter_runtime
""".lstrip()
    )
    (capture_root / "adapter-runtime.yml").write_text(capture_body)
    test_dir = tmp_path / "tests" / "sample"
    test_dir.mkdir(parents=True)
    (test_dir / "test_example.py").write_text(
        """
import pytest


@pytest.mark.regression_capture("existing-case")
def test_existing_case():
    assert True


class TestCaptured:
    @pytest.mark.regression_capture("existing-case")
    def test_method_case(self):
        assert True
""".lstrip()
    )
    return capture_root


def valid_capture_body() -> str:
    return """
schema_version: 1
area: adapter-runtime
captures:
  - id: existing-case
    title: Existing case remains discoverable
    area: adapter-runtime
    bug_class: scan_safety
    owner_surface: core_runtime_policy
    severity: P2
    current_tests:
      - tests/sample/test_example.py::test_existing_case
      - tests/sample/test_example.py::TestCaptured::test_method_case
    carryover_gates:
      - gate: adapter_testkit_regression_carryover
        status: pending
        expected_suite: scan_safety
    notes: Current tests cover this regression.
""".lstrip()


def test_validator_accepts_well_formed_capture_rows(tmp_path: Path) -> None:
    capture_root = write_capture_project(tmp_path, valid_capture_body())
    script = load_script()

    assert script.validate(capture_root=capture_root, repo_root=tmp_path) == []


def test_validator_rejects_duplicate_ids_and_unknown_capture_files(tmp_path: Path) -> None:
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures:
  - id: duplicate-case
    title: First row
    area: adapter-runtime
    bug_class: scan_safety
    owner_surface: core_runtime_policy
    severity: P2
    current_tests:
      - tests/sample/test_example.py::test_existing_case
    carryover_gates:
      - gate: adapter_testkit_regression_carryover
        status: pending
  - id: duplicate-case
    title: Second row
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
    (capture_root / "unexpected.yml").write_text("schema_version: 1\ncaptures: []\n")
    script = load_script()

    errors = script.validate(capture_root=capture_root, repo_root=tmp_path)

    assert any("duplicate capture id 'duplicate-case'" in error for error in errors)
    assert any("unexpected capture file" in error and "unexpected.yml" in error for error in errors)


def test_validator_rejects_missing_fields_invalid_gate_and_status(tmp_path: Path) -> None:
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures:
  - id: invalid-row
    title: Invalid row
    area: adapter-runtime
    severity: P2
    current_tests:
      - tests/sample/test_example.py::test_existing_case
    carryover_gates:
      - gate: missing_gate
        status: invalid_status
""".lstrip(),
    )
    script = load_script()

    errors = script.validate(capture_root=capture_root, repo_root=tmp_path)

    assert any("missing required field 'bug_class'" in error for error in errors)
    assert any("missing required field 'owner_surface'" in error for error in errors)
    assert any("unknown carryover gate 'missing_gate'" in error for error in errors)
    assert any("invalid status 'invalid_status'" in error for error in errors)


@pytest.mark.regression_capture("regression-capture-decision-advisory-metadata-routing")
def test_validator_rejects_invalid_path_surface_routing(tmp_path: Path) -> None:
    capture_root = write_capture_project(tmp_path, valid_capture_body())
    index_path = capture_root / "index.yml"
    index_path.write_text(
        index_path.read_text().replace(
            "        - adapter_runtime",
            "        - missing_surface",
            1,
        )
    )
    script = load_script()

    errors = script.validate(capture_root=capture_root, repo_root=tmp_path)

    assert any("unknown trigger surface 'missing_surface'" in error for error in errors)


def test_validator_rejects_stale_pytest_node_references(tmp_path: Path) -> None:
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures:
  - id: stale-test-reference
    title: Stale test reference
    area: adapter-runtime
    bug_class: scan_safety
    owner_surface: core_runtime_policy
    severity: P2
    current_tests:
      - tests/sample/test_example.py::test_missing_case
      - tests/sample/missing_file.py::test_missing_file
    carryover_gates:
      - gate: adapter_testkit_regression_carryover
        status: pending
""".lstrip(),
    )
    script = load_script()

    errors = script.validate(capture_root=capture_root, repo_root=tmp_path)

    assert any(
        "pytest node not found" in error and "test_missing_case" in error for error in errors
    )
    assert any(
        "test file does not exist" in error and "missing_file.py" in error for error in errors
    )


def test_validator_rejects_tests_without_matching_regression_capture_marker(
    tmp_path: Path,
) -> None:
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures:
  - id: missing-marker
    title: Missing marker
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
    script = load_script()

    errors = script.validate(capture_root=capture_root, repo_root=tmp_path)

    assert any(
        "missing @pytest.mark.regression_capture('missing-marker')" in error for error in errors
    )


@pytest.mark.regression_capture("regression-capture-orphan-marker-guard")
def test_validator_rejects_regression_capture_markers_without_capture_rows(
    tmp_path: Path,
) -> None:
    capture_root = write_capture_project(tmp_path, valid_capture_body())
    (tmp_path / "tests" / "sample" / "test_orphan.py").write_text(
        """
import pytest


@pytest.mark.regression_capture("orphan-marker")
def test_orphan_marker_case():
    assert True
""".lstrip()
    )
    script = load_script()

    errors = script.validate(capture_root=capture_root, repo_root=tmp_path)

    assert any("orphan regression_capture marker 'orphan-marker'" in error for error in errors)


@pytest.mark.regression_capture("regression-capture-orphan-marker-guard")
def test_validator_rejects_regression_capture_markers_missing_from_current_tests(
    tmp_path: Path,
) -> None:
    capture_root = write_capture_project(tmp_path, valid_capture_body())
    (tmp_path / "tests" / "sample" / "test_missing_current_test.py").write_text(
        """
import pytest


@pytest.mark.regression_capture("existing-case")
def test_marked_but_unlisted_case():
    assert True
""".lstrip()
    )
    script = load_script()

    errors = script.validate(capture_root=capture_root, repo_root=tmp_path)

    assert any(
        "test_missing_current_test.py::test_marked_but_unlisted_case" in error
        and "not listed in current_tests" in error
        for error in errors
    )


def test_validator_rejects_statuses_without_required_references(tmp_path: Path) -> None:
    capture_root = write_capture_project(
        tmp_path,
        """
schema_version: 1
area: adapter-runtime
captures:
  - id: deferred-without-rationale
    title: Deferred row
    area: adapter-runtime
    bug_class: scan_safety
    owner_surface: core_runtime_policy
    severity: P2
    current_tests:
      - tests/sample/test_example.py::test_existing_case
    carryover_gates:
      - gate: adapter_testkit_regression_carryover
        status: deferred
  - id: migrated-without-tests
    title: Migrated row
    area: adapter-runtime
    bug_class: scan_safety
    owner_surface: core_runtime_policy
    severity: P2
    current_tests:
      - tests/sample/test_example.py::test_existing_case
    carryover_gates:
      - gate: adapter_testkit_regression_carryover
        status: migrated
""".lstrip(),
    )
    script = load_script()

    errors = script.validate(capture_root=capture_root, repo_root=tmp_path)

    assert any("status 'deferred' requires rationale" in error for error in errors)
    assert any("status 'migrated' requires migrated_tests" in error for error in errors)


def test_validator_reports_malformed_yaml(tmp_path: Path) -> None:
    capture_root = write_capture_project(tmp_path, valid_capture_body())
    (capture_root / "adapter-runtime.yml").write_text("captures: [\n")
    script = load_script()

    errors = script.validate(capture_root=capture_root, repo_root=tmp_path)

    assert any("invalid YAML" in error for error in errors)
