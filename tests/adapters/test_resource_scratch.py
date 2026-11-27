"""Owned scratch coordination on synthetic private local directories."""

import os
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
    _SessionTicket,
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
@pytest.mark.parametrize(
    "damage",
    [
        "marker",
        "missing-lock",
        "unexpected-entry",
        "nested-spill",
        "replaced-lock",
        "replaced-spill",
    ],
)
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
        os.chmod(ticket.path / "worker.lock", 0o600)
        (ticket.path / "worker.old").unlink()
    elif damage == "replaced-spill":
        original = root.ticket.path.parent / "old-spill"
        (ticket.path / "spill").rename(original)
        (ticket.path / "spill").mkdir(mode=0o700)
        sentinel = original / "keep.tmp"
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
from recon_core.adapters._resource_scratch import (
    _Identity, _RootTicket, _SessionTicket, _ScratchRoot
)
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


@pytest.mark.regression_capture("owned-scratch-two-lease-recovery")
def test_parent_crash_before_worker_claim(root: _ScratchRoot, tmp_path: Path) -> None:
    from uuid import UUID

    marker = tmp_path / "published"
    r = root.ticket
    script = """
import sys
import time
from pathlib import Path
from uuid import UUID
from recon_core.adapters._resource_scratch import _Identity, _RootTicket, _ScratchRoot
r = _RootTicket(
    Path(sys.argv[1]), UUID(sys.argv[2]),
    _Identity(int(sys.argv[3]), int(sys.argv[4])),
    _Identity(int(sys.argv[5]), int(sys.argv[6])),
)
parent = _ScratchRoot(r).create_session()
s = parent.ticket
parts = [s.nonce.hex]
for identity in (s.identity, s.parent_identity, s.worker_identity, s.spill_identity):
    parts.extend((str(identity.device), str(identity.inode)))
marker = Path(sys.argv[7])
temporary = marker.with_suffix(".tmp")
temporary.write_text(":".join(parts), encoding="ascii")
temporary.replace(marker)
time.sleep(120)
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(r.path),
            str(r.nonce),
            str(r.identity.device),
            str(r.identity.inode),
            str(r.lock_identity.device),
            str(r.lock_identity.inode),
            str(marker),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists() and process.poll() is None
        nonce, *values = marker.read_text(encoding="ascii").split(":")
        identities = tuple(_Identity(int(values[i]), int(values[i + 1])) for i in range(0, 8, 2))
        ticket = _SessionTicket(
            r.path / nonce, UUID(nonce), identities[0], identities[1], identities[2], identities[3]
        )
        assert root.recover(ticket) is _Recovery.LIVE
        process.kill()
        process.wait(timeout=10)
        restarted = _ScratchRoot.reopen(root.ticket.path)
        assert restarted.recover_abandoned().removed == 1
        assert not ticket.path.exists()
        with pytest.raises(_ScratchError):
            root.claim_worker(ticket)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


@pytest.mark.regression_capture("owned-scratch-discovery")
def test_reopen_and_discover_abandoned_sessions(root: _ScratchRoot) -> None:
    abandoned = root.create_session()
    live = root.create_session()
    incomplete = root.ticket.path / "unrecognized"
    incomplete.mkdir()
    (incomplete / "keep").write_bytes(b"keep")
    abandoned.release()
    try:
        reopened = _ScratchRoot.reopen(root.ticket.path)
        assert reopened.ticket == root.ticket
        summary = reopened.recover_abandoned()
        assert (summary.removed, summary.live, summary.retained) == (1, 1, 1)
        assert not abandoned.ticket.path.exists()
        assert live.ticket.path.exists()
        assert (incomplete / "keep").read_bytes() == b"keep"
        assert not hasattr(summary, "paths")
    finally:
        live.release()


@pytest.mark.regression_capture("owned-scratch-discovery")
@pytest.mark.parametrize("damage", ["oversized", "wrong-root", "wrong-session", "missing-marker"])
def test_discovery_rejects_unverified_marker(root: _ScratchRoot, damage: str) -> None:
    parent = root.create_session()
    ticket = parent.ticket
    parent.release()
    marker = ticket.path / "owner"
    if damage == "oversized":
        marker.write_bytes(b"9" * 4096)
    elif damage == "wrong-root":
        parts = marker.read_bytes().split(b":")
        parts[1] = b"0" * 32
        marker.write_bytes(b":".join(parts))
    elif damage == "wrong-session":
        parts = marker.read_bytes().split(b":")
        parts[2] = b"0" * 32
        marker.write_bytes(b":".join(parts))
    else:
        marker.unlink()
    summary = _ScratchRoot.reopen(root.ticket.path).recover_abandoned()
    assert summary.removed == 0 and summary.retained == 1
    assert ticket.path.exists()


@pytest.mark.regression_capture("owned-scratch-discovery")
def test_reopen_rejects_replaced_root_lock(root: _ScratchRoot) -> None:
    lock = root.ticket.path / "root.lock"
    old = root.ticket.path / "old.lock"
    lock.rename(old)
    lock.write_bytes(b"\0")
    os.chmod(lock, 0o600)
    old.unlink()
    with pytest.raises(_ScratchError):
        _ScratchRoot.reopen(root.ticket.path)


def test_reopen_never_adopts_plain_directory(tmp_path: Path) -> None:
    path = tmp_path.resolve() / "arbitrary"
    path.mkdir(mode=0o700)
    sentinel = path / "keep"
    sentinel.write_bytes(b"keep")
    with pytest.raises(_ScratchError):
        _ScratchRoot.reopen(path)
    assert sentinel.read_bytes() == b"keep"


@pytest.mark.regression_capture("owned-scratch-discovery")
def test_partial_deletion_is_retained(root: _ScratchRoot, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = root.create_session()
    ticket = parent.ticket
    parent.release()
    (ticket.path / "spill" / "fixture.tmp").write_bytes(b"spill")
    original = Path.unlink

    def interrupted(path: Path, missing_ok: bool = False) -> None:
        if path == ticket.path / "worker.lock":
            raise OSError("PRIVATE_SENTINEL")
        original(path, missing_ok=missing_ok)

    with monkeypatch.context() as context:
        context.setattr(Path, "unlink", interrupted)
        summary = root.recover_abandoned()
    assert summary.removed == 0 and summary.retained == 1
    assert ticket.path.exists()
    summary = _ScratchRoot.reopen(root.ticket.path).recover_abandoned()
    assert summary.removed == 0 and summary.retained == 1
    assert ticket.path.exists()


@pytest.mark.regression_capture("owned-scratch-two-lease-recovery")
def test_lock_permission_error_is_not_live_owner(
    root: _ScratchRoot, monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno

    from recon_core.adapters import _resource_scratch as scratch

    parent = root.create_session()

    def denied(fd: int) -> None:
        raise PermissionError(errno.EACCES, "PRIVATE_SENTINEL")

    try:
        monkeypatch.setattr(scratch, "_lock_exclusive", denied)
        with pytest.raises(_ScratchError) as lock_error:
            scratch._FileLease.acquire(root.ticket.path / "root.lock", root.ticket.lock_identity)
        assert not isinstance(lock_error.value, scratch._BusyError)
        # A denied root lock is uncertainty, not evidence of a live owner.
        assert root.recover(parent.ticket) is _Recovery.RETAINED
        with pytest.raises(_ScratchError) as caught:
            root.claim_worker(parent.ticket)
        assert "PRIVATE_SENTINEL" not in str(caught.value)
    finally:
        parent.release()


@pytest.mark.regression_capture("owned-scratch-two-lease-recovery")
def test_check_scratch_independent_current_directories(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch

    base = tmp_path.resolve()
    first = _resource_scratch._create_check_scratch(base)
    second = _resource_scratch._create_check_scratch(base)
    assert first.path != second.path
    assert first.path.parent == second.path.parent == base
    assert not list(first.path.iterdir())
    assert not list(second.path.iterdir())

    first_file = first.path / "first.tmp"
    second_file = second.path / "second.tmp"
    first_file.write_bytes(b"first")
    second_file.write_bytes(b"second")
    first.cleanup(native_closed=True)
    assert not first.path.exists()
    assert second_file.read_bytes() == b"second"
    second.cleanup(native_closed=True)
    assert not second.path.exists()
    assert not list(base.iterdir())


@pytest.mark.regression_capture("owned-scratch-two-lease-recovery")
def test_check_scratch_requires_confirmed_native_close(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch

    scratch = _resource_scratch._create_check_scratch(tmp_path.resolve())
    data = scratch.path / "fixture.tmp"
    data.write_bytes(b"live")
    with pytest.raises(_ScratchError):
        scratch.cleanup(native_closed=False)
    assert data.read_bytes() == b"live"
    scratch.cleanup(native_closed=True)
    assert not scratch.path.exists()


@pytest.mark.regression_capture("owned-scratch-untrusted-retained")
def test_check_scratch_replaced_directory_is_not_deleted(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch

    base = tmp_path.resolve()
    scratch = _resource_scratch._create_check_scratch(base)
    original = base / "original"
    (scratch.path / "original.tmp").write_bytes(b"original")
    scratch.path.rename(original)
    scratch.path.mkdir(mode=0o700)
    replacement = scratch.path / "replacement.tmp"
    replacement.write_bytes(b"unrelated")

    with pytest.raises(_ScratchError):
        scratch.cleanup(native_closed=True)

    assert replacement.read_bytes() == b"unrelated"
    assert (original / "original.tmp").read_bytes() == b"original"


@pytest.mark.regression_capture("owned-scratch-untrusted-retained")
def test_check_scratch_cleanup_failure_is_safe_and_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from recon_core.adapters import _resource_scratch

    scratch = _resource_scratch._create_check_scratch(tmp_path.resolve())
    data = scratch.path / "fixture.tmp"
    data.write_bytes(b"retain")

    def denied(*args, **kwargs):
        raise PermissionError("PRIVATE_SENTINEL")

    monkeypatch.setattr(shutil, "rmtree", denied)
    with pytest.raises(_ScratchError) as caught:
        scratch.cleanup(native_closed=True)

    assert data.read_bytes() == b"retain"
    assert "PRIVATE_SENTINEL" not in str(caught.value)
    assert str(scratch.path) not in str(caught.value)


@pytest.mark.regression_capture("owned-scratch-discovery")
def test_check_scratch_never_adopts_or_sweeps_existing_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from recon_core.adapters import _resource_scratch

    base = tmp_path.resolve()
    old = base / "recon-scratch-abandoned"
    old.mkdir()
    old_file = old / "old.tmp"
    old_file.write_bytes(b"abandoned")
    unrelated = base / "unrelated.txt"
    unrelated.write_bytes(b"unrelated")

    def forbidden(*args, **kwargs):
        raise AssertionError("Creation must not scan the existing base.")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "iterdir", forbidden)
        scratch = _resource_scratch._create_check_scratch(base)
    assert scratch.path != old
    assert scratch.path.parent == base
    scratch.cleanup(native_closed=True)

    assert old_file.read_bytes() == b"abandoned"
    assert unrelated.read_bytes() == b"unrelated"


@pytest.mark.regression_capture("owned-scratch-discovery")
def test_check_scratch_abrupt_exit_leaves_residue_without_blocking_next_check(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch

    base = tmp_path.resolve()
    code = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "from recon_core.adapters._resource_scratch import _create_check_scratch\n"
        "scratch = _create_check_scratch(Path(sys.argv[1]))\n"
        "(scratch.path / 'abandoned.tmp').write_bytes(b'abandoned')\n"
        "os._exit(0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(base)],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, "Synthetic abrupt-exit fixture failed."
    abandoned = list(base.iterdir())
    assert len(abandoned) == 1
    residue = abandoned[0] / "abandoned.tmp"
    assert residue.read_bytes() == b"abandoned"

    current = _resource_scratch._create_check_scratch(base)
    assert current.path != abandoned[0]
    current.cleanup(native_closed=True)
    assert residue.read_bytes() == b"abandoned"


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.parametrize("base_kind", ["missing", "file"])
def test_check_scratch_requires_existing_directory(tmp_path: Path, base_kind: str) -> None:
    from recon_core.adapters import _resource_scratch

    base = tmp_path.resolve() / "PRIVATE_SENTINEL"
    if base_kind == "file":
        base.write_bytes(b"unrelated")
    with pytest.raises(_ScratchError) as caught:
        _resource_scratch._create_check_scratch(base)
    assert "PRIVATE_SENTINEL" not in str(caught.value)
    if base_kind == "file":
        assert base.read_bytes() == b"unrelated"
    else:
        assert not base.exists()


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.skipif(os.name != "posix", reason="POSIX private directory mode")
def test_check_scratch_uses_private_posix_directory(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch

    scratch = _resource_scratch._create_check_scratch(tmp_path.resolve())
    try:
        info = scratch.path.stat()
        assert info.st_uid == os.geteuid()
        assert info.st_mode & 0o777 == 0o700
    finally:
        scratch.cleanup(native_closed=True)


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.skipif(os.name != "posix", reason="POSIX parent rename protection")
def test_check_scratch_rejects_unprotected_writable_base(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch

    base = tmp_path.resolve() / "unsafe"
    base.mkdir()
    base.chmod(0o777)
    try:
        with pytest.raises(_ScratchError):
            _resource_scratch._create_check_scratch(base)
        assert not list(base.iterdir())
    finally:
        base.chmod(0o700)


@pytest.mark.regression_capture("owned-scratch-untrusted-retained")
@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink cleanup fixture")
def test_check_scratch_cleanup_never_follows_unrelated_symlink(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch

    base = tmp_path.resolve()
    unrelated = base / "unrelated"
    unrelated.mkdir()
    sentinel = unrelated / "keep"
    sentinel.write_bytes(b"keep")
    scratch = _resource_scratch._create_check_scratch(base)
    (scratch.path / "link").symlink_to(unrelated, target_is_directory=True)
    scratch.cleanup(native_closed=True)
    assert not scratch.path.exists()
    assert sentinel.read_bytes() == b"keep"


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS actual inherited ACL")
def test_check_scratch_removes_inherited_macos_grants(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch
    from recon_core.adapters._scratch_namespace import _darwin_no_acl_grants

    base = tmp_path.resolve() / "acl-parent"
    base.mkdir(mode=0o700)
    subprocess.run(
        ["chmod", "+a", "everyone allow list,search,file_inherit,directory_inherit", str(base)],
        capture_output=True,
        timeout=15,
        check=True,
    )
    scratch = _resource_scratch._create_check_scratch(base)
    try:
        assert _darwin_no_acl_grants(scratch.path, scratch.path.lstat())
        assert scratch.path.stat().st_mode & 0o777 == 0o700
    finally:
        scratch.cleanup(native_closed=True)


@pytest.mark.regression_capture("windows-scratch-private-acl")
@pytest.mark.skipif(sys.platform != "win32", reason="Windows actual inherited ACL")
def test_check_scratch_protects_windows_directory_and_file(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch
    from recon_core.adapters._windows_scratch_security import (
        _verify_private_directory,
        _verify_private_file,
    )

    base = tmp_path.resolve() / "acl-parent"
    base.mkdir()
    subprocess.run(
        ["icacls", str(base), "/grant", "*S-1-1-0:(OI)(CI)RX"],
        capture_output=True,
        timeout=15,
        check=True,
    )
    scratch = _resource_scratch._create_check_scratch(base)
    try:
        _verify_private_directory(scratch.path)
        file = scratch.path / "fixture.tmp"
        file.write_bytes(b"synthetic")
        _verify_private_file(file)
    finally:
        scratch.cleanup(native_closed=True)
