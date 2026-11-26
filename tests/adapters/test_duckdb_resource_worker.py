"""Private isolated worker control lifecycle, not project admission."""

import importlib.util
import io
import os
import struct
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from recon_core.adapters.duckdb._resource_worker import _WorkerProcess, _stop_process
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
    worker = subprocess.Popen(
        [sys.executable, "-m", "recon_core.adapters.duckdb._resource_worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert worker.stdin is not None and worker.stdout is not None
        assert _read_control(worker.stdout) == _ControlPacket(_ControlKind.READY, 0)
        _write_control(worker.stdin, _ControlPacket(_ControlKind.PROBE, 2))
        assert worker.wait(timeout=15) != 0
        assert worker.stdout.read(1) == b""
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait(timeout=10)
        if worker.stdin is not None:
            worker.stdin.close()
        if worker.stdout is not None:
            worker.stdout.close()


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
        assert worker.close() == result
    finally:
        worker.abort()


def test_abort_reaps_actual_worker() -> None:
    worker = _WorkerProcess()
    try:
        worker.open()
        result = worker.abort()
        assert result.confirmed_exit and not result.clean_close
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
        Path(sys.argv[1]).write_text(str(worker.pid), encoding="ascii")
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
