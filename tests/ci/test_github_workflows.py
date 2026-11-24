import shlex
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_ci_gates_duckdb_semantics() -> None:
    workflow = yaml.safe_load(
        (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["duckdb-semantics"]
    steps = {step["name"]: step for step in job["steps"]}

    install = steps["Install package with DuckDB extra"]
    semantic = steps["Test DuckDB semantic coverage"]

    assert 'python -m pip install -e ".[dev,duckdb]"' in install["run"].splitlines()
    assert semantic["env"]["RECON_REQUIRE_DUCKDB_TESTS"] == "1"
    assert shlex.split(semantic["run"]) == [
        "pytest",
        "tests/adapters",
        "tests/check_engine",
        "tests/services",
        "tests/cli",
    ]
    for required in (job, install, semantic):
        assert "if" not in required
        assert not required.get("continue-on-error", False)


def test_ci_gates_representative_duckdb_versions() -> None:
    workflow = yaml.safe_load(
        (_REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    jobs = workflow["jobs"]
    assert jobs["duckdb-semantics"]["strategy"]["matrix"]["python-version"] == [
        "3.11",
        "3.12",
        "3.13",
    ]
    job = jobs["duckdb-version-compatibility"]
    assert job["strategy"]["fail-fast"] is False
    assert job["strategy"]["matrix"]["include"] == [
        {"duckdb-version": "1.0.0", "numeric-selection": "not bignum"},
        {"duckdb-version": "1.3.2", "numeric-selection": "not bignum"},
        {"duckdb-version": "1.4.5", "numeric-selection": ""},
        {"duckdb-version": "2.0.1", "numeric-selection": ""},
    ]
    steps = {step["name"]: step for step in job["steps"]}
    assert steps["Set up Python"]["with"]["python-version"] == "3.11"
    install = steps["Install pinned DuckDB"]
    semantic = steps["Test existing and numeric semantic coverage"]
    assert install["env"]["DUCKDB_VERSION"] == "${{ matrix.duckdb-version }}"
    install_command = 'python -m pip install -e ".[dev,duckdb]" "duckdb==${DUCKDB_VERSION}"'
    assert install_command in install["run"].splitlines()
    assert semantic["env"] == {
        "RECON_REQUIRE_DUCKDB_TESTS": "1",
        "NUMERIC_SELECTION": "${{ matrix.numeric-selection }}",
    }
    assert semantic["run"].splitlines() == [
        "status=0",
        "pytest tests/adapters tests/check_engine tests/services tests/cli "
        "--ignore=tests/adapters/test_duckdb_aggregate_numeric_domains.py || status=1",
        'if [ -n "$NUMERIC_SELECTION" ]; then',
        "  pytest -s tests/adapters/test_duckdb_aggregate_numeric_domains.py "
        '-k "$NUMERIC_SELECTION" || status=1',
        "else",
        "  pytest -s tests/adapters/test_duckdb_aggregate_numeric_domains.py || status=1",
        "fi",
        'exit "$status"',
    ]
    for required in (job, install, semantic):
        assert "if" not in required
        assert not required.get("continue-on-error", False)
