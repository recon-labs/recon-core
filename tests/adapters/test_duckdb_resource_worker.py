"""Private isolated worker control lifecycle, not project admission."""

import importlib.util
import io
import os
import struct
import subprocess
import sys
import textwrap
import time
from contextlib import suppress
from pathlib import Path

import pytest

from recon_core.adapters.duckdb._resource_worker import _stop_process, _WorkerProcess
from recon_core.adapters.duckdb._worker_control_protocol import (
    _ControlError,
    _ControlKind,
    _ControlPacket,
    _read_control,
    _write_control,
)


@pytest.fixture
def native_available() -> None:
    if importlib.util.find_spec("duckdb") is None:
        if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
            pytest.fail("Required worker tests need the DuckDB extra.")
        pytest.skip("DuckDB extra not installed")


@pytest.mark.regression_capture("duckdb-worker-control-protocol")
def test_worker_control_packet_is_closed_and_bounded() -> None:
    packet = _ControlPacket(_ControlKind.RECOMMENDATIONS, 1, 128 << 20, 2)
    stream = io.BytesIO()
    _write_control(stream, packet)
    data = stream.getvalue()
    assert len(data) == struct.calcsize(">4sBQqq")
    assert _read_control(io.BytesIO(data)) == packet
    for end in range(len(data)):
        with pytest.raises(_ControlError):
            _read_control(io.BytesIO(data[:end]))
    for offset in (0, 4):
        bad = bytearray(data)
        bad[offset] = 255
        with pytest.raises(_ControlError):
            _read_control(io.BytesIO(bad))
    with pytest.raises(_ControlError):
        _write_control(io.BytesIO(), _ControlPacket(_ControlKind.CLOSE, 1, 7, 0))


@pytest.mark.regression_capture("duckdb-worker-control-protocol")
def test_worker_rejects_stale_sequence_before_native_work() -> None:
    worker = _WorkerProcess()
    try:
        worker.open()
        child = worker._process
        assert child is not None and child.stdin is not None and child.stdout is not None
        _write_control(child.stdin, _ControlPacket(_ControlKind.PROBE, 2))
        assert child.wait(timeout=15) != 0
        assert child.stdout.read(1) == b""
    finally:
        worker.abort()


@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
def test_worker_termination_confirmation(native_available: None) -> None:
    worker = _WorkerProcess()
    try:
        worker.open()
        assert worker.pid is not None and worker.pid != os.getpid()
        recommendations = worker.recommendations()
        assert recommendations.memory_bytes is not None and recommendations.memory_bytes > 0
        assert recommendations.threads is not None and recommendations.threads > 0
        result = worker.close()
        assert result.confirmed_exit and result.clean_close and result.returncode == 0
        assert result.pipes_released
        assert worker.close() == result
    finally:
        worker.abort()


def test_abort_reaps_actual_worker() -> None:
    worker = _WorkerProcess()
    try:
        worker.open()
        result = worker.abort()
        assert result.confirmed_exit and not result.clean_close
        assert result.pipes_released
        assert result.returncode is not None
        assert worker.abort() == result
    finally:
        worker.abort()


@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
def test_stop_request_is_not_confirmed_exit() -> None:
    class Stubborn:
        def __init__(self) -> None:
            self.signals: list[str] = []

        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            self.signals.append("terminate")

        def kill(self) -> None:
            self.signals.append("kill")

        def wait(self, timeout: float) -> int:
            raise subprocess.TimeoutExpired("private", timeout)

    child = Stubborn()
    result = _stop_process(child, timeout=0.01)
    assert child.signals == ["terminate", "kill"]
    assert not result.confirmed_exit and result.returncode is None


@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
def test_parent_death_liveness(tmp_path: Path, native_available: None) -> None:
    psutil = pytest.importorskip("psutil")
    marker = tmp_path / "worker-id"
    code = textwrap.dedent(
        """
        import sys
        import time
        from pathlib import Path
        from recon_core.adapters.duckdb._resource_worker import _WorkerProcess

        worker = _WorkerProcess()
        worker.open()
        worker.recommendations()
        marker = Path(sys.argv[1])
        temporary = marker.with_suffix(".tmp")
        temporary.write_text(str(worker.pid), encoding="ascii")
        temporary.replace(marker)
        while True:
            time.sleep(1)
        """
    )
    parent = subprocess.Popen(
        [sys.executable, "-c", code, str(marker)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    child = None
    try:
        deadline = time.monotonic() + 30
        while not marker.exists() and parent.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists() and parent.poll() is None
        child = psutil.Process(int(marker.read_text(encoding="ascii")))
        parent.kill()
        parent.wait(timeout=10)
        deadline = time.monotonic() + 15
        while child.is_running() and time.monotonic() < deadline:
            try:
                if child.status() == psutil.STATUS_ZOMBIE:
                    break
            except psutil.NoSuchProcess:
                break
            time.sleep(0.02)
        with suppress(psutil.NoSuchProcess):
            assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=10)
        if child is not None and child.is_running():
            try:
                if child.status() != psutil.STATUS_ZOMBIE:
                    child.kill()
            except psutil.NoSuchProcess:
                pass


@pytest.mark.regression_capture("duckdb-worker-control-protocol")
def test_worker_repeated_probe_invalidates_child(native_available: None) -> None:
    worker = _WorkerProcess()
    try:
        worker.open()
        worker.recommendations()
        with pytest.raises(_ControlError):
            worker.recommendations()
        assert worker.abort().confirmed_exit
        with pytest.raises(_ControlError):
            worker.open()
    finally:
        worker.abort()


@pytest.mark.regression_capture("duckdb-worker-process-lifecycle")
def test_parent_eof_interrupts_busy_control_handler(tmp_path: Path) -> None:
    marker = tmp_path / "busy"
    code = textwrap.dedent(
        """
        import sys
        import time
        from pathlib import Path
        from recon_core.adapters.duckdb import _resource_worker as worker

        def blocked_probe():
            Path(sys.argv[1]).touch()
            time.sleep(120)
            raise AssertionError("Busy probe unexpectedly finished")

        worker._recommendations = blocked_probe
        worker._main()
        """
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(marker)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert child.stdin is not None
        _write_control(child.stdin, _ControlPacket(_ControlKind.PROBE, 1))
        deadline = time.monotonic() + 15
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists() and child.poll() is None
        child.stdin.close()
        assert child.wait(timeout=15) == 75
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        if child.stdin is not None:
            child.stdin.close()
        if child.stdout is not None:
            child.stdout.close()
