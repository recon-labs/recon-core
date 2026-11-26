"""Owned scratch coordination on synthetic private local directories."""

import subprocess
import sys
import time
from pathlib import Path

import pytest

from recon_core.adapters._resource_scratch import (
    _Identity,
    _Recovery,
    _ScratchError,
    _ScratchRoot,
)


@pytest.fixture
def root(tmp_path: Path) -> _ScratchRoot:
    # A synthetic test directory, not production filesystem/ACL qualification.
    return _ScratchRoot.create(tmp_path.resolve() / "private")


@pytest.mark.regression_capture("owned-scratch-two-lease-recovery")
def test_owned_scratch_recovery(root: _ScratchRoot) -> None:
    parent = root.create_session()
    ticket = parent.ticket
    worker = root.claim_worker(ticket)
    (ticket.path / "spill" / "synthetic.tmp").write_bytes(b"spill")
    try:
        assert root.recover(ticket) is _Recovery.LIVE
        assert parent.cleanup(worker_exit_confirmed=False) is _Recovery.RETAINED
        assert (ticket.path / "spill" / "synthetic.tmp").exists()
        worker.release()
        assert root.recover(ticket) is _Recovery.LIVE
        assert parent.cleanup(worker_exit_confirmed=True) is _Recovery.REMOVED
        assert not ticket.path.exists()
        with pytest.raises(_ScratchError):
            root.claim_worker(ticket)
    finally:
        worker.release()
        parent.release()


@pytest.mark.regression_capture("owned-scratch-two-lease-recovery")
def test_scratch_live_owner_races(root: _ScratchRoot) -> None:
    parent = root.create_session()
    ticket = parent.ticket
    worker = root.claim_worker(ticket)
    try:
        with pytest.raises(_ScratchError):
            root.claim_worker(ticket)
        parent.release()
        assert root.recover(ticket) is _Recovery.LIVE
        assert ticket.path.exists()
        worker.release()
        assert root.recover(ticket) is _Recovery.REMOVED
    finally:
        worker.release()
        parent.release()


@pytest.mark.regression_capture("owned-scratch-untrusted-retained")
@pytest.mark.parametrize("damage", ["marker", "missing-lock", "unexpected-entry", "nested-spill", "replaced-lock", "replaced-spill"])
def test_untrusted_scratch_never_deleted(root: _ScratchRoot, damage: str) -> None:
    parent = root.create_session()
    ticket = parent.ticket
    sentinel = ticket.path / "spill" / "keep.tmp"
    sentinel.write_bytes(b"keep")
    parent.release()
    if damage == "marker":
        (ticket.path / "owner").write_bytes(b"unknown")
    elif damage == "missing-lock":
        (ticket.path / "worker.lock").unlink()
    elif damage == "unexpected-entry":
        (ticket.path / "unowned").write_bytes(b"keep")
    elif damage == "replaced-lock":
        (ticket.path / "worker.lock").rename(ticket.path / "worker.old")
        (ticket.path / "worker.lock").write_bytes(b"\0")
        (ticket.path / "worker.old").unlink()
    elif damage == "replaced-spill":
        (ticket.path / "spill").rename(ticket.path / "old-spill")
        (ticket.path / "spill").mkdir(mode=0o700)
        sentinel = ticket.path / "old-spill" / "keep.tmp"
    else:
        (ticket.path / "spill" / "nested").mkdir()
    assert root.recover(ticket) is _Recovery.RETAINED
    assert sentinel.read_bytes() == b"keep"


def test_scratch_symlink_is_retained(root: _ScratchRoot, tmp_path: Path) -> None:
    outside = tmp_path / "unrelated"
    outside.mkdir()
    sentinel = outside / "keep"
    sentinel.write_bytes(b"keep")
    parent = root.create_session()
    ticket = parent.ticket
    parent.release()
    try:
        (ticket.path / "spill" / "link").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable in this environment")
    assert root.recover(ticket) is _Recovery.RETAINED
    assert sentinel.read_bytes() == b"keep"


def test_existing_namespace_not_adopted(root: _ScratchRoot) -> None:
    with pytest.raises(_ScratchError):
        _ScratchRoot.create(root.ticket.path)


def test_worker_claim_requires_live_parent(root: _ScratchRoot) -> None:
    parent = root.create_session()
    ticket = parent.ticket
    parent.release()
    with pytest.raises(_ScratchError):
        root.claim_worker(ticket)
    assert root.recover(ticket) is _Recovery.REMOVED


@pytest.mark.regression_capture("owned-scratch-two-lease-recovery")
def test_actual_child_lease_prevents_recovery_until_exit(
    root: _ScratchRoot, tmp_path: Path
) -> None:
    parent = root.create_session()
    ticket = parent.ticket
    marker = tmp_path / "claimed"
    # Synthetic test-only arguments; the runtime transport must not put
    # real paths or authored values in argv.
    script = """
import sys
import time
from pathlib import Path
from uuid import UUID
from recon_core.adapters._resource_scratch import _Identity, _RootTicket, _SessionTicket, _ScratchRoot
def identity(index):
    return _Identity(int(sys.argv[index]), int(sys.argv[index + 1]))
r = _RootTicket(Path(sys.argv[1]), UUID(sys.argv[2]), identity(3), identity(5))
s = _SessionTicket(
    Path(sys.argv[7]), UUID(sys.argv[8]), identity(9), identity(11), identity(13), identity(15)
)
lease = _ScratchRoot(r).claim_worker(s)
Path(sys.argv[17]).touch()
time.sleep(120)
"""
    r = root.ticket

    def parts(identity: _Identity) -> list[str]:
        return [str(identity.device), str(identity.inode)]

    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(r.path),
            str(r.nonce),
            *parts(r.identity),
            *parts(r.lock_identity),
            str(ticket.path),
            str(ticket.nonce),
            *parts(ticket.identity),
            *parts(ticket.parent_identity),
            *parts(ticket.worker_identity),
            *parts(ticket.spill_identity),
            str(marker),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists() and child.poll() is None
        parent.release()
        assert root.recover(ticket) is _Recovery.LIVE
        child.kill()
        child.wait(timeout=10)
        assert root.recover(ticket) is _Recovery.REMOVED
        with pytest.raises(_ScratchError):
            root.claim_worker(ticket)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        parent.release()
