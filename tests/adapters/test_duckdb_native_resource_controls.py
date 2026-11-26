"""Native setting assignment and readback are not physical quota proof."""

import importlib
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from recon_core.adapters.duckdb._native_resource_controls import (
    _apply_native_controls,
    _native_startup_config,
    _NativeControlError,
    _NativeControlRequest,
    _parse_native_size,
    _read_native_recommendations,
)

_MIB = 1 << 20


@pytest.mark.parametrize(
    ("display", "lower", "upper"),
    [
        ("0 bytes", 0, 0),
        ("1 byte", 1, 1),
        ("1023 bytes", 1023, 1023),
        ("1.0 KiB", 1024, 1126),
        ("128.0 MiB", 128 * _MIB, 128 * _MIB + (_MIB - 1) // 10),
        ("1.2 MB", 1200000, 1299999),
        ("1.0 GiB", 1 << 30, (1 << 30) + ((1 << 30) - 1) // 10),
    ],
)
def test_native_size_display_interval(display: str, lower: int, upper: int) -> None:
    interval = _parse_native_size(display)
    assert interval is not None
    assert (interval.lower_bytes, interval.upper_bytes) == (lower, upper)


@pytest.mark.parametrize(
    "display",
    [
        None,
        True,
        -1,
        "90% of available disk space",
        "unlimited",
        "PRIVATE_SENTINEL",
        "1.00 MiB",
        "1e3 MiB",
        "0.1 MiB",
        "1.0 XB",
        "9999999999999999999999 PiB",
        "1.0 bytes",
    ],
)
def test_unknown_native_size_is_not_unlimited(display: object) -> None:
    assert _parse_native_size(display) is None


class _FakeConnection:
    def __init__(self, scratch: Path) -> None:
        self.calls: list[str] = []
        self.values: dict[str, object] = {
            "memory_limit": "128.0 MiB",
            "threads": 2,
            "max_temp_directory_size": "1.0 MiB",
            "temp_directory": str(scratch),
        }
        self.fail: str | None = None

    def execute(self, sql: str) -> SimpleNamespace:
        self.calls.append(sql)
        if self.fail is not None and self.fail in sql:
            raise RuntimeError("PRIVATE_SENTINEL")
        if sql.startswith("SET "):
            return SimpleNamespace()
        setting = sql.split("'")[1]
        return SimpleNamespace(fetchmany=lambda count: [(self.values[setting],)])


@pytest.mark.regression_capture("duckdb-native-resource-control-readback")
def test_spill_setting_is_applied_after_connect(tmp_path: Path) -> None:
    request = _NativeControlRequest(128 * _MIB, 2, _MIB, tmp_path)
    config = _native_startup_config(request)
    assert config == {
        "memory_limit": f"{128 * _MIB} bytes",
        "threads": "2",
        "temp_directory": str(tmp_path),
    }
    native = _FakeConnection(tmp_path)
    result = _apply_native_controls(native, request)
    assert native.calls[0] == f"SET max_temp_directory_size = '{_MIB} bytes'"
    assert set(native.calls[1:]) == {
        "SELECT current_setting('memory_limit')",
        "SELECT current_setting('threads')",
        "SELECT current_setting('max_temp_directory_size')",
        "SELECT current_setting('temp_directory')",
    }
    assert result.memory.lower_bytes == 128 * _MIB
    assert result.threads == 2
    assert result.spill.lower_bytes == _MIB
    assert not result.enforcement_proven


@pytest.mark.regression_capture("duckdb-native-resource-control-readback")
@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("memory_limit", "256.0 MiB"),
        ("threads", 3),
        ("threads", True),
        ("max_temp_directory_size", "0 bytes"),
        ("max_temp_directory_size", "90% of available disk space"),
        ("temp_directory", "PRIVATE_SENTINEL"),
    ],
)
def test_required_control_readback_mismatch(
    tmp_path: Path, setting: str, value: object
) -> None:
    native = _FakeConnection(tmp_path)
    native.values[setting] = value
    with pytest.raises(_NativeControlError) as caught:
        _apply_native_controls(native, _NativeControlRequest(128 * _MIB, 2, _MIB, tmp_path))
    assert "PRIVATE_SENTINEL" not in str(caught.value)


def test_native_setup_error_is_sanitized(tmp_path: Path) -> None:
    native = _FakeConnection(tmp_path)
    native.fail = "SET max_temp_directory_size"
    with pytest.raises(_NativeControlError) as caught:
        _apply_native_controls(native, _NativeControlRequest(128 * _MIB, 2, _MIB, tmp_path))
    assert "PRIVATE_SENTINEL" not in str(caught.value)
    assert len(native.calls) == 1


def test_native_recommendation_partial_not_required_proof(tmp_path: Path) -> None:
    native = _FakeConnection(tmp_path)
    native.values["memory_limit"] = "PRIVATE_SENTINEL"
    result = _read_native_recommendations(native)
    assert result.memory_bytes is None
    assert result.threads == 2
    assert "PRIVATE_SENTINEL" not in repr(result)
    assert not any(call.startswith("SET ") for call in native.calls)


@pytest.mark.parametrize(
    ("memory", "threads", "spill"),
    [
        (0, 1, 0),
        (True, 1, 0),
        (1, 0, 0),
        (1, True, 0),
        (1, 1, -1),
        (1, 1, True),
        (1 << 63, 1, 0),
        (1, 1 << 63, 0),
    ],
)
def test_invalid_native_targets_do_not_reach_native(
    tmp_path: Path, memory: int, threads: int, spill: int
) -> None:
    with pytest.raises(_NativeControlError):
        _NativeControlRequest(memory, threads, spill, tmp_path)


def test_native_byte_target_floors_without_small_arbitrary_cap(tmp_path: Path) -> None:
    requested = (1 << 63) - 1
    request = _NativeControlRequest(requested, 1, requested, tmp_path)
    assert 0 < request.memory_bytes <= requested
    assert request.memory_bytes == int(float(request.memory_bytes))
    assert request.spill_bytes == request.memory_bytes
    assert request.memory_bytes > (1 << 62)


def test_native_zero_spill_readback_is_not_proof_of_no_spill(tmp_path: Path) -> None:
    native = _FakeConnection(tmp_path)
    native.values["max_temp_directory_size"] = "0 bytes"
    result = _apply_native_controls(native, _NativeControlRequest(128 * _MIB, 2, 0, tmp_path))
    assert result.spill.lower_bytes == result.spill.upper_bytes == 0
    assert not result.enforcement_proven


@pytest.fixture
def duckdb() -> Any:
    if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
        try:
            return importlib.import_module("duckdb")
        except ImportError:
            pytest.fail("Required native control tests need .[dev,duckdb].", pytrace=False)
    return pytest.importorskip("duckdb")


def test_native_control_application(tmp_path: Path, duckdb: Any) -> None:
    database = tmp_path / "fixture.duckdb"
    scratch = tmp_path / "owned scratch"
    scratch.mkdir()
    connection = duckdb.connect(str(database))
    try:
        connection.execute("CREATE TABLE fixture AS SELECT 42 AS value")
    finally:
        connection.close()

    request = _NativeControlRequest(128 * _MIB + 17, 1, _MIB + 19, scratch)
    native = duckdb.connect(str(database), read_only=True, config=_native_startup_config(request))
    try:
        actual = _apply_native_controls(native, request)
        assert actual.memory.lower_bytes <= request.memory_bytes <= actual.memory.upper_bytes
        assert actual.threads == request.threads
        assert actual.spill.lower_bytes <= request.spill_bytes <= actual.spill.upper_bytes
        assert native.execute("SELECT value FROM fixture").fetchone() == (42,)
        assert not actual.enforcement_proven
    finally:
        native.close()


def test_native_recommendations_on_empty_instance(duckdb: Any) -> None:
    native = duckdb.connect(":memory:")
    try:
        result = _read_native_recommendations(native)
        assert result.memory_bytes is not None and result.memory_bytes > 0
        assert result.threads is not None and result.threads > 0
    finally:
        native.close()


@pytest.mark.parametrize("rows", [[], [(1,), (2,)], [(1, 2)], [None], "PRIVATE_SENTINEL"])
def test_malformed_native_setting_shape_is_not_a_recommendation(rows: object) -> None:
    native = SimpleNamespace(
        execute=lambda sql: SimpleNamespace(fetchmany=lambda count: rows)
    )
    result = _read_native_recommendations(native)
    assert result.memory_bytes is None
    assert result.threads is None
