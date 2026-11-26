"""Private isolated DuckDB process bootstrap and confirmed-stop lifecycle.

Only the native recommendation probe and close are implemented here. User
database binding and data work require the later owned-session protocol.
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from importlib import import_module
from queue import Empty, Queue
from threading import Lock, Thread
from typing import BinaryIO, Protocol

from recon_core.adapters.duckdb._native_resource_controls import (
    _NativeRecommendations,
    _read_native_recommendations,
)
from recon_core.adapters.duckdb._worker_control_protocol import (
    _ControlError,
    _ControlKind,
    _ControlPacket,
    _read_control,
    _write_control,
)


class _ChildProcess(Protocol):
    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float) -> int: ...


@dataclass(frozen=True, slots=True)
class _WorkerStop:
    confirmed_exit: bool
    returncode: int | None
    clean_close: bool = False
    pipes_released: bool = False


def _wait_for_exit(process: _ChildProcess, timeout: float) -> _WorkerStop:
    try:
        return _WorkerStop(True, process.wait(timeout=timeout))
    except (OSError, subprocess.TimeoutExpired):
        return _WorkerStop(False, None)


def _stop_process(process: _ChildProcess, *, timeout: float) -> _WorkerStop:
    """Signal only the owned process, never report a signal as confirmed exit."""
    try:
        if process.poll() is not None:
            return _wait_for_exit(process, timeout)
    except OSError:
        pass
    for signal in (process.terminate, process.kill):
        try:
            signal()
        except OSError:
            # Exit can race the signal; only the subsequent wait is proof.
            pass
        result = _wait_for_exit(process, timeout)
        if result.confirmed_exit:
            return result
    return _WorkerStop(False, None)


class _WorkerProcess:
    """Single-use bootstrap, one control exchange at a time.

    These deadlines apply only to startup, metadata and shutdown, never
    to a future workload. A failed exchange cannot be retried on this child.
    """

    def __init__(self, *, control_timeout: float = 30.0, stop_timeout: float = 5.0) -> None:
        self._control_timeout = control_timeout
        self._stop_timeout = stop_timeout
        self._attempted = False
        self._sequence = 0
        self._process: subprocess.Popen[bytes] | None = None
        self._stop: _WorkerStop | None = None
        self._control_lock = Lock()
        self._stop_lock = Lock()
        self._reader: Thread | None = None

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    def _receive(self, kind: _ControlKind, sequence: int) -> _ControlPacket:
        process = self._process
        if process is None or process.stdout is None:
            raise _ControlError()
        stream = process.stdout
        received: Queue[_ControlPacket | None] = Queue(maxsize=1)

        def read() -> None:
            try:
                received.put_nowait(_read_control(stream))
            except Exception:
                received.put_nowait(None)

        self._reader = Thread(target=read, daemon=True)
        self._reader.start()
        try:
            packet = received.get(timeout=self._control_timeout)
        except Empty:
            raise _ControlError() from None
        if packet is None or packet.kind is not kind or packet.sequence != sequence:
            raise _ControlError()
        return packet

    def open(self) -> None:
        if self._attempted or self._stop is not None:
            raise _ControlError()
        self._attempted = True
        try:
            self._process = subprocess.Popen(
                [sys.executable, "-m", "recon_core.adapters.duckdb._resource_worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                bufsize=0,
            )
            self._receive(_ControlKind.READY, 0)
        except Exception:
            self.abort()
            raise _ControlError() from None
        except BaseException:
            self.abort()
            raise

    def _exchange(self, request: _ControlKind, response: _ControlKind) -> _ControlPacket:
        if not self._control_lock.acquire(blocking=False):
            raise _ControlError()
        try:
            process = self._process
            if process is None or process.stdin is None or self._stop is not None:
                raise _ControlError()
            self._sequence += 1
            _write_control(process.stdin, _ControlPacket(request, self._sequence))
            return self._receive(response, self._sequence)
        finally:
            self._control_lock.release()

    def recommendations(self) -> _NativeRecommendations:
        try:
            packet = self._exchange(_ControlKind.PROBE, _ControlKind.RECOMMENDATIONS)
        except BaseException:
            self.abort()
            raise
        return _NativeRecommendations(
            memory_bytes=None if packet.first == -1 else packet.first,
            threads=None if packet.second == -1 else packet.second,
        )

    def _release_pipes(self) -> bool:
        # Never close a pipe under an active blocking reader. A lingering
        # reader is an incomplete transport cleanup, not clean release.
        if self._reader is not None:
            self._reader.join(timeout=self._stop_timeout)
            if self._reader.is_alive():
                return False
        released = True
        if self._process is not None:
            for stream in (self._process.stdin, self._process.stdout):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        released = False
        return released

    def abort(self) -> _WorkerStop:
        with self._stop_lock:
            if self._stop is not None and self._stop.confirmed_exit:
                if not self._stop.pipes_released:
                    self._stop = _WorkerStop(
                        True, self._stop.returncode, pipes_released=self._release_pipes()
                    )
                return self._stop
            process = self._process
            if process is None:
                self._stop = _WorkerStop(False, None)
            else:
                self._stop = _stop_process(process, timeout=self._stop_timeout)
                if self._stop.confirmed_exit:
                    self._stop = _WorkerStop(
                        True, self._stop.returncode, pipes_released=self._release_pipes()
                    )
            return self._stop

    def close(self) -> _WorkerStop:
        if self._stop is not None:
            return self.abort()
        try:
            self._exchange(_ControlKind.CLOSE, _ControlKind.CLOSED)
            process = self._process
            if process is None:
                raise _ControlError()
            stopped = _wait_for_exit(process, self._stop_timeout)
            if stopped.confirmed_exit and stopped.returncode == 0:
                with self._stop_lock:
                    released = self._release_pipes()
                    self._stop = _WorkerStop(True, 0, clean_close=released, pipes_released=released)
                    return self._stop
        except (OSError, _ControlError):
            pass
        except BaseException:
            self.abort()
            raise
        return self.abort()


def _recommendations() -> _NativeRecommendations:
    duckdb = import_module("duckdb")
    connection = duckdb.connect(":memory:", config={"temp_directory": ""})
    try:
        return _read_native_recommendations(connection)
    finally:
        connection.close()


def _serve(commands: BinaryIO, responses: BinaryIO) -> None:
    pending: Queue[_ControlPacket] = Queue(maxsize=1)
    guard = Lock()
    active = False

    def watch() -> None:
        nonlocal active
        sequence = 0
        try:
            while True:
                packet = _read_control(commands)
                if packet.kind not in (_ControlKind.PROBE, _ControlKind.CLOSE):
                    raise _ControlError()
                if packet.sequence != sequence + 1:
                    raise _ControlError()
                sequence = packet.sequence
                with guard:
                    if active:
                        raise _ControlError()
                    active = True
                    pending.put_nowait(packet)
        except Exception:
            # EOF is a parent-liveness signal independent of the native
            # call. Best effort: a suspended/GIL-blocked process may not run
            # this watchdog. No physical containment guarantee is claimed.
            os._exit(75)

    Thread(target=watch, daemon=True).start()
    _write_control(responses, _ControlPacket(_ControlKind.READY, 0))
    probed = False
    while True:
        request = pending.get()
        if request.kind is _ControlKind.CLOSE:
            _write_control(responses, _ControlPacket(_ControlKind.CLOSED, request.sequence))
            return
        if probed:
            raise _ControlError()
        probed = True
        try:
            facts = _recommendations()
            response = _ControlPacket(
                _ControlKind.RECOMMENDATIONS,
                request.sequence,
                -1 if facts.memory_bytes is None else facts.memory_bytes,
                -1 if facts.threads is None else facts.threads,
            )
        except Exception:
            _write_control(responses, _ControlPacket(_ControlKind.ERROR, request.sequence))
            raise _ControlError() from None
        with guard:
            _write_control(responses, response)
            active = False


def _main() -> None:
    # The protocol owns a duplicate of the inherited stdout pipe. Native
    # and Python stdout/stderr must not be treated as framed messages.
    try:
        protocol_fd = os.dup(1)
        with open(os.devnull, "wb", buffering=0) as discard:
            os.dup2(discard.fileno(), 1)
            os.dup2(discard.fileno(), 2)
        with os.fdopen(protocol_fd, "wb", buffering=0) as responses:
            with os.fdopen(0, "rb", buffering=0, closefd=False) as commands:
                _serve(commands, responses)
    except BaseException:
        os._exit(76)
    os._exit(0)


if __name__ == "__main__":
    _main()
