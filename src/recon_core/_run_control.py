"""Invocation-local cooperative stop state; no native or service ownership."""

from collections.abc import Callable
from enum import StrEnum
from threading import Condition, Event, Thread
from typing import TypeVar

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


class _StopCause(StrEnum):
    CANCELLED = "run_cancelled"
    DEADLINE = "run_deadline_exceeded"

    def diagnostic(self) -> Diagnostic:
        if self is _StopCause.CANCELLED:
            code = "RC_RUNTIME_RUN_CANCELLED"
            message = "Run cancellation was requested."
        else:
            code = "RC_RUNTIME_RUN_DEADLINE_EXCEEDED"
            message = "Run invocation deadline was exceeded."
        return Diagnostic(
            code=code,
            severity=DiagnosticSeverity.ERROR,
            message=message,
            resource_type="run_invocation",
            hint="Start a new invocation when ready.",
        )


_T = TypeVar("_T")


class _RunStopped(RuntimeError):
    def __init__(self, cause: _StopCause) -> None:
        super().__init__(cause.diagnostic().message)
        self.cause = cause


class _RunControl:
    """Latch the first observed stop; a final seal cannot be changed."""

    def __init__(
        self,
        *,
        started_ns: int,
        timeout_seconds: int | None,
        cancel_event: Event | None,
        clock: Callable[[], int],
    ) -> None:
        self._deadline_ns = (
            started_ns + timeout_seconds * 1_000_000_000 if timeout_seconds is not None else None
        )
        self._cancel_event = cancel_event
        self._clock = clock
        self._lock = Condition()
        self._active: Callable[[], bool] | None = None
        self._borrowed = False
        self._observer: Thread | None = None
        self._closing = False
        self._cause: _StopCause | None = None
        self._sealed = False

    def _observe_locked(self) -> _StopCause | None:
        if self._sealed or self._cause is not None:
            return self._cause
        if self._cancel_event is not None and self._cancel_event.is_set():
            self._cause = _StopCause.CANCELLED
        elif self._deadline_ns is not None and self._clock() >= self._deadline_ns:
            self._cause = _StopCause.DEADLINE
        return self._cause

    def observe(self) -> _StopCause | None:
        with self._lock:
            return self._observe_locked()

    def seal(self) -> _StopCause | None:
        self.close_observer()
        with self._lock:
            cause = self._observe_locked()
            self._sealed = True
            return cause

    def checkpoint(self) -> None:
        if (cause := self.observe()) is not None:
            raise _RunStopped(cause)

    def native_call(self, call: Callable[[], _T], interrupt: Callable[[], bool]) -> _T:
        """Borrow only the active call; wait for interrupt return before releasing it."""
        with self._lock:
            if (cause := self._observe_locked()) is not None:
                raise _RunStopped(cause)
            if self._active is not None or self._closing or self._sealed:
                raise RuntimeError("Invalid invocation native call ownership.")
            if self._observer is None:
                observer = Thread(target=self._watch, name="recon-run-control", daemon=False)
                observer.start()
                self._observer = observer
            self._active = interrupt
            self._lock.notify_all()
        try:
            self.checkpoint()
            result = call()
        finally:
            with self._lock:
                self._active = None
                self._lock.notify_all()
                while self._borrowed:
                    self._lock.wait()
        self.checkpoint()
        return result

    def _watch(self) -> None:
        while True:
            with self._lock:
                if self._closing:
                    return
                cause = self._observe_locked()
                interrupt = self._active if cause is not None else None
                if interrupt is None:
                    self._lock.wait(timeout=0.01)
                    continue
                self._borrowed = True
            try:
                interrupt()
            except Exception:
                # An interrupt request is not proof of termination. Keep observing
                # the same active lease, never retry the query or close its handle.
                pass
            finally:
                with self._lock:
                    self._borrowed = False
                    self._lock.notify_all()
                    if self._active is interrupt:
                        self._lock.wait(timeout=0.01)

    def close_observer(self) -> None:
        with self._lock:
            self._closing = True
            self._lock.notify_all()
            observer = self._observer
        if observer is not None:
            observer.join()
