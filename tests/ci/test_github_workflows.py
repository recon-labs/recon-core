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
