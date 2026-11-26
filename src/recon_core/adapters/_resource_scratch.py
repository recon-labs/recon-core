"""Private scratch coordination on a caller-qualified local filesystem.

This collaborator does not qualify filesystem locking semantics, Windows ACLs
or the stable per-project namespace. Those are prerequisites to activation.
Only cooperative owners using the root lock may change the namespace.
"""

import errno
import os
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import IO
from uuid import UUID, uuid4


class _ScratchError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Owned scratch storage could not be verified.")


class _Busy(_ScratchError):
    pass


class _Recovery(Enum):
    REMOVED = auto()
    LIVE = auto()
    RETAINED = auto()


@dataclass(frozen=True, slots=True)
class _Identity:
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class _RootTicket:
    path: Path = field(repr=False)
    nonce: UUID
    identity: _Identity
    lock_identity: _Identity


@dataclass(frozen=True, slots=True)
class _SessionTicket:
    path: Path = field(repr=False)
    nonce: UUID
    identity: _Identity
    parent_identity: _Identity
    worker_identity: _Identity
    spill_identity: _Identity


def _identity(info: os.stat_result) -> _Identity:
    if info.st_ino <= 0:
        raise _ScratchError()
    return _Identity(info.st_dev, info.st_ino)


def _inspect(path: Path, *, directory: bool) -> os.stat_result:
    info = path.lstat()
    if (
        not path.is_absolute()
        or path.resolve(strict=True) != path
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
        or (not directory and info.st_nlink != 1)
    ):
        raise _ScratchError()
    # POSIX ownership/mode proof only. Windows ACL qualification remains
    # an explicit prerequisite of the eventual runtime root provider.
    if os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise _ScratchError()
    return info


def _write_new(path: Path, data: bytes) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        stream.write(data)


def _marker(path: Path, expected: bytes) -> None:
    info = _inspect(path, directory=False)
    if info.st_size != len(expected):
        raise _ScratchError()
    with path.open("rb") as stream:
        if _identity(os.fstat(stream.fileno())) != _identity(info):
            raise _ScratchError()
        if stream.read(len(expected) + 1) != expected:
            raise _ScratchError()


def _identity_text(identity: _Identity) -> str:
    return f"{identity.device}:{identity.inode}"


def _root_marker(ticket: _RootTicket) -> bytes:
    return (
        f"RC-SCRATCH-1:{ticket.nonce.hex}:{_identity_text(ticket.identity)}:"
        f"{_identity_text(ticket.lock_identity)}"
    ).encode("ascii")


def _session_marker(root: _RootTicket, session: _SessionTicket) -> bytes:
    return (
        f"RC-SESSION-1:{root.nonce.hex}:{session.nonce.hex}:"
        + ":".join(
            _identity_text(identity)
            for identity in (
                session.identity,
                session.parent_identity,
                session.worker_identity,
                session.spill_identity,
            )
        )
    ).encode("ascii")


class _FileLease:
    """An independent non-inherited OS lock on a pre-existing single-byte file."""

    def __init__(self, stream: IO[bytes]) -> None:
        self._stream = stream

    @classmethod
    def acquire(cls, path: Path, expected: _Identity) -> "_FileLease":
        info = _inspect(path, directory=False)
        if info.st_size != 1 or _identity(info) != expected:
            raise _ScratchError()
        stream = path.open("r+b", buffering=0)
        try:
            if _identity(os.fstat(stream.fileno())) != _identity(info):
                raise _ScratchError()
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                elif os.name == "posix":
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    raise _ScratchError()
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK):
                    raise _Busy() from None
                raise _ScratchError() from None
            stream.seek(0)
            if stream.read(1) != b"\0":
                raise _ScratchError()
            return cls(stream)
        except BaseException:
            stream.close()
            raise

    def release(self) -> None:
        self._stream.close()


class _ParentLease:
    def __init__(self, root: "_ScratchRoot", ticket: _SessionTicket, lock: _FileLease) -> None:
        self._root = root
        self.ticket = ticket
        self._lock = lock

    def release(self) -> None:
        """Abandon ownership; never delete files."""
        self._lock.release()

    def cleanup(self, *, worker_exit_confirmed: bool) -> _Recovery:
        if worker_exit_confirmed is not True:
            return _Recovery.RETAINED
        try:
            with self._root._guard():
                self.release()
                return self._root._recover_locked(self.ticket)
        except (OSError, _ScratchError):
            return _Recovery.RETAINED


class _ScratchRoot:
    """Root lock serializes publication, claims and deletion, not queries."""

    def __init__(self, ticket: _RootTicket) -> None:
        self.ticket = ticket

    @classmethod
    def create(cls, path: Path) -> "_ScratchRoot":
        """Create an exclusive root, never adopt an arbitrary existing directory."""
        try:
            if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent:
                raise _ScratchError()
            path.mkdir(mode=0o700)
            _write_new(path / "root.lock", b"\0")
            ticket = _RootTicket(
                path, uuid4(), _identity(_inspect(path, directory=True)),
                _identity(_inspect(path / "root.lock", directory=False)),
            )
            _write_new(path / "owner", _root_marker(ticket))
            return cls(ticket)
        except (OSError, RuntimeError, ValueError):
            raise _ScratchError() from None

    def _verify_root(self) -> None:
        if _identity(_inspect(self.ticket.path, directory=True)) != self.ticket.identity:
            raise _ScratchError()
        _marker(self.ticket.path / "owner", _root_marker(self.ticket))

    @contextmanager
    def _guard(self) -> Iterator[None]:
        self._verify_root()
        # Internal coordination deadline; no workload deadline.
        deadline = time.monotonic() + 5
        while True:
            try:
                lock = _FileLease.acquire(self.ticket.path / "root.lock", self.ticket.lock_identity)
                break
            except _Busy:
                if time.monotonic() >= deadline:
                    raise _ScratchError() from None
                time.sleep(0.02)
        try:
            self._verify_root()
            yield
        finally:
            lock.release()

    def _verify_session(self, ticket: _SessionTicket) -> None:
        if (
            ticket.path != self.ticket.path / ticket.nonce.hex
            or _identity(_inspect(ticket.path, directory=True)) != ticket.identity
            or ticket.identity.device != self.ticket.identity.device
        ):
            raise _ScratchError()
        _marker(ticket.path / "owner", _session_marker(self.ticket, ticket))
        spill = _inspect(ticket.path / "spill", directory=True)
        if (
            _identity(spill) != ticket.spill_identity
            or spill.st_dev != ticket.identity.device
            or (ticket.path / "spill").is_mount()
            or _identity(_inspect(ticket.path / "parent.lock", directory=False))
            != ticket.parent_identity
            or _identity(_inspect(ticket.path / "worker.lock", directory=False))
            != ticket.worker_identity
        ):
            raise _ScratchError()

    def create_session(self) -> _ParentLease:
        try:
            with self._guard():
                nonce = uuid4()
                path = self.ticket.path / nonce.hex
                path.mkdir(mode=0o700)
                (path / "spill").mkdir(mode=0o700)
                _write_new(path / "parent.lock", b"\0")
                _write_new(path / "worker.lock", b"\0")
                ticket = _SessionTicket(
                    path, nonce, _identity(_inspect(path, directory=True)),
                    _identity(_inspect(path / "parent.lock", directory=False)),
                    _identity(_inspect(path / "worker.lock", directory=False)),
                    _identity(_inspect(path / "spill", directory=True)),
                )
                parent = _FileLease.acquire(path / "parent.lock", ticket.parent_identity)
                try:
                    # Publish only after the parent's lease is held.
                    _write_new(path / "owner", _session_marker(self.ticket, ticket))
                    self._verify_session(ticket)
                    return _ParentLease(self, ticket, parent)
                except BaseException:
                    parent.release()
                    raise
        except (OSError, RuntimeError, ValueError):
            # Partial creation is retained, not swept without complete proof.
            raise _ScratchError() from None

    def claim_worker(self, ticket: _SessionTicket) -> _FileLease:
        try:
            with self._guard():
                self._verify_session(ticket)
                try:
                    abandoned = _FileLease.acquire(ticket.path / "parent.lock", ticket.parent_identity)
                except _Busy:
                    return _FileLease.acquire(ticket.path / "worker.lock", ticket.worker_identity)
                abandoned.release()
                raise _ScratchError()
        except (OSError, RuntimeError, ValueError):
            raise _ScratchError() from None

    def recover(self, ticket: _SessionTicket) -> _Recovery:
        """Only recover a positively identified inactive session."""
        try:
            with self._guard():
                return self._recover_locked(ticket)
        except (OSError, RuntimeError, ValueError):
            return _Recovery.RETAINED

    def _recover_locked(self, ticket: _SessionTicket) -> _Recovery:
        self._verify_session(ticket)
        try:
            parent = _FileLease.acquire(ticket.path / "parent.lock", ticket.parent_identity)
        except _Busy:
            return _Recovery.LIVE
        try:
            try:
                worker = _FileLease.acquire(ticket.path / "worker.lock", ticket.worker_identity)
            except _Busy:
                return _Recovery.LIVE
            try:
                files = self._deletion_plan(ticket)
            finally:
                worker.release()
        finally:
            parent.release()
        # Both handles must be closed before deletion on Windows. The root
        # lock is still held; no cooperating late worker can claim the session.
        self._verify_session(ticket)
        for path in files:
            path.unlink()
        (ticket.path / "spill").rmdir()
        for name in ("parent.lock", "worker.lock", "owner"):
            (ticket.path / name).unlink()
        ticket.path.rmdir()
        return _Recovery.REMOVED

    def _deletion_plan(self, ticket: _SessionTicket) -> tuple[Path, ...]:
        if {entry.name for entry in ticket.path.iterdir()} != {
            "owner", "parent.lock", "worker.lock", "spill"
        }:
            raise _ScratchError()
        # DuckDB spill files need not have owner-only modes when the enclosing
        # private directory is inaccessible to other users. Never follow links,
        # hardlinks, reparse points, unexpected directories or special files.
        files = tuple((ticket.path / "spill").iterdir())
        for path in files:
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_dev != ticket.identity.device
                or path.resolve(strict=True) != path
                or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                or (os.name == "posix" and info.st_uid != os.getuid())
            ):
                raise _ScratchError()
        return files
