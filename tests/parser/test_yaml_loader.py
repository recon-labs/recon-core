from pathlib import Path

import pytest

from recon_core.diagnostics import DiagnosticSeverity
from recon_core.parser import SourceLocation, load_yaml_file, load_yaml_text


def test_source_location_serializes_path_and_position() -> None:
    location = SourceLocation(path="contracts/customer_revenue.yml", line=3, column=5)

    assert location.to_dict() == {
        "path": "contracts/customer_revenue.yml",
        "line": 3,
        "column": 5,
    }


def test_load_yaml_text_returns_loaded_data_without_diagnostics() -> None:
    result = load_yaml_text(
        """
name: customer_revenue
source:
  connection: legacy
""".lstrip(),
        path="contracts/customer_revenue.yml",
    )

    assert result.succeeded
    assert result.data == {
        "name": "customer_revenue",
        "source": {"connection": "legacy"},
    }
    assert result.diagnostics == ()


def test_load_yaml_file_reads_utf8_file(tmp_path: Path) -> None:
    yaml_file = tmp_path / "contracts" / "customer_revenue.yml"
    yaml_file.parent.mkdir()
    yaml_file.write_text("name: customer_revenue\n", encoding="utf-8")

    result = load_yaml_file(yaml_file)

    assert result.succeeded
    assert result.data == {"name": "customer_revenue"}
    assert result.diagnostics == ()


@pytest.mark.regression_capture("yaml-diagnostic-redaction")
@pytest.mark.regression_capture("yaml-profile-and-source-privacy")
def test_load_yaml_text_reports_invalid_yaml() -> None:
    result = load_yaml_text(
        "name: customer_revenue\nsource: select * from customers where ssn: secret-ssn\n",
        path="contracts/customer_revenue.yml",
    )

    assert not result.succeeded
    assert result.data is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_INVALID_YAML"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.message == "Invalid YAML in resource file."
    assert diagnostic.path == "contracts/customer_revenue.yml"
    assert diagnostic.line is not None
    assert diagnostic.column is not None
    assert diagnostic.hint == "Fix the YAML syntax in this resource file."
    assert "secret-ssn" not in diagnostic.message
    assert "select * from customers" not in diagnostic.message


@pytest.mark.regression_capture("yaml-loader-duplicate-key-protection")
def test_load_yaml_text_reports_duplicate_yaml_keys() -> None:
    result = load_yaml_text(
        """
name: customer_revenue
name: duplicate_customer_revenue
""".lstrip(),
        path="contracts/customer_revenue.yml",
    )

    assert not result.succeeded
    assert result.data is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_INVALID_YAML"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == "contracts/customer_revenue.yml"
    assert diagnostic.line is not None
    assert diagnostic.column is not None
    assert diagnostic.message == "Invalid YAML in resource file: duplicate YAML key."


@pytest.mark.regression_capture("yaml-loader-duplicate-key-protection")
def test_load_yaml_text_reports_unhashable_mapping_keys() -> None:
    result = load_yaml_text(
        """
? [name, alias]
: customer_revenue
""".lstrip(),
        path="contracts/customer_revenue.yml",
    )

    assert not result.succeeded
    assert result.data is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_INVALID_YAML"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == "contracts/customer_revenue.yml"
    assert diagnostic.line is not None
    assert diagnostic.column is not None
    assert diagnostic.message == "Invalid YAML in resource file: unsupported YAML mapping key."


def test_load_yaml_file_reports_unreadable_file(tmp_path: Path) -> None:
    yaml_file = tmp_path / "contracts" / "missing.yml"

    result = load_yaml_file(yaml_file)

    assert not result.succeeded
    assert result.data is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_FILE_READ_ERROR"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == str(yaml_file)
    assert diagnostic.hint == "Check that the resource file exists and is readable."


def test_load_yaml_file_reports_non_utf8_file_as_read_error(tmp_path: Path) -> None:
    yaml_file = tmp_path / "contracts" / "customer_revenue.yml"
    yaml_file.parent.mkdir()
    yaml_file.write_bytes(b"\xff\xfe\xfa")

    result = load_yaml_file(yaml_file)

    assert not result.succeeded
    assert result.data is None
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_FILE_READ_ERROR"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.path == str(yaml_file)
    assert diagnostic.hint == "Check that the resource file exists and is readable."
