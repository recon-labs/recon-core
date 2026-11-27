"""Temporary synthetic CI evidence for intermittent resource-control refusal."""

from pathlib import Path
from typing import Any

import pytest

from recon_core.adapters.duckdb import _bound_execution as binding


@pytest.fixture(autouse=True)
def trace_adaptive_control_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    calculate = binding._adaptive_native_request
    apply = binding._apply_native_controls
    create_scratch = binding._create_check_scratch

    def traced_calculation(
        connection: Any, scratch: Path, policy: Any
    ) -> binding._NativeControlRequest:
        try:
            return calculate(connection, scratch, policy)
        except (ValueError, binding._NativeControlError) as exc:
            print("Synthetic adaptive calculation refused:", str(exc))
            raise

    def traced_controls(
        connection: Any, request: binding._NativeControlRequest, **kwargs: Any
    ) -> Any:
        try:
            return apply(connection, request, **kwargs)
        except binding._NativeControlError as exc:
            readback = tuple(
                connection.execute(f"SELECT current_setting('{setting}')").fetchone()
                for setting in ("memory_limit", "threads", "max_temp_directory_size")
            )
            print("Synthetic control refusal:", str(exc), repr(request), repr(readback))
            raise

    def traced_scratch(base: Path) -> Any:
        try:
            return create_scratch(base)
        except binding._ScratchError:
            print("Synthetic scratch verification refused")
            raise

    monkeypatch.setattr(binding, "_adaptive_native_request", traced_calculation)
    monkeypatch.setattr(binding, "_apply_native_controls", traced_controls)
    monkeypatch.setattr(binding, "_create_check_scratch", traced_scratch)
