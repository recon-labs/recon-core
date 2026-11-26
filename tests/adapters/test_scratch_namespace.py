"""Stable private scratch namespace candidate, not runtime admission."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from recon_core.adapters._scratch_namespace import (
    _namespace_path,
    _NamespaceError,
    _open_namespace,
)


@pytest.mark.regression_capture("scratch-namespace-qualification")
def test_stable_project_namespace_and_recovery(tmp_path: Path) -> None:
    base = tmp_path.resolve()
    project = base / "project"
    project.mkdir()
    first = _open_namespace(base, project)
    other_project = base / "another"
    other_project.mkdir()
    other = _open_namespace(base, other_project)
    assert first.ticket.path != other.ticket.path
    abandoned = first.create_session()
    abandoned.release()
    second = _open_namespace(base, project)
    assert first.ticket == second.ticket
    assert second.recover_abandoned().removed == 1
    assert other.ticket.path.is_dir()


@pytest.mark.regression_capture("scratch-namespace-qualification")
def test_namespace_does_not_adopt_arbitrary_directory(tmp_path: Path) -> None:
    base = tmp_path.resolve()
    project = base / "project"
    project.mkdir()
    path = _namespace_path(base, project)
    path.mkdir(mode=0o700)
    sentinel = path / "keep"
    sentinel.write_bytes(b"keep")
    with pytest.raises(_NamespaceError):
        _open_namespace(base, project)
    assert sentinel.read_bytes() == b"keep"


@pytest.mark.regression_capture("scratch-namespace-qualification")
def test_unknown_filesystem_does_not_authorize_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from recon_core.adapters import _scratch_namespace as namespace
    from recon_core.adapters._scratch_filesystem import _FilesystemEvidence

    base = tmp_path.resolve()
    project = base / "project"
    project.mkdir()
    path = _namespace_path(base, project)
    monkeypatch.setattr(
        namespace, "_observe_scratch_filesystem", lambda path: _FilesystemEvidence()
    )
    with pytest.raises(_NamespaceError):
        _open_namespace(base, project)
    assert not path.exists()


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode proof")
def test_broadened_namespace_is_retained(tmp_path: Path) -> None:
    base = tmp_path.resolve()
    root = _open_namespace(base, base)
    parent = root.create_session()
    parent.release()
    parent.ticket.path.chmod(0o755)
    assert root.recover_abandoned().retained == 1
    assert parent.ticket.path.exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin ACL proof")
def test_darwin_extended_acl_is_not_private(tmp_path: Path) -> None:
    base = tmp_path.resolve()
    root = _open_namespace(base, base)
    result = subprocess.run(
        ["chmod", "+a", "everyone allow list,search", str(root.ticket.path)],
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    with pytest.raises(_NamespaceError):
        _open_namespace(base, base)
    assert root.ticket.path.is_dir()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory ACL proof")
def test_windows_session_has_protected_acl(tmp_path: Path) -> None:
    from recon_core.adapters._windows_scratch_security import _verify_private_directory

    base = tmp_path.resolve()
    root = _open_namespace(base, base)
    parent = root.create_session()
    try:
        _verify_private_directory(root.ticket.path)
        _verify_private_directory(parent.ticket.path)
        _verify_private_directory(parent.ticket.path / "spill")
    finally:
        parent.release()


@pytest.mark.regression_capture("scratch-namespace-qualification")
def test_changed_mount_retains_existing_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    from recon_core.adapters import _scratch_namespace as namespace

    base = tmp_path.resolve()
    root = _open_namespace(base, base)
    parent = root.create_session()
    parent.release()
    real = namespace._observe_scratch_filesystem

    def changed(path: Path) -> object:
        facts = real(path)
        return replace(facts, mount_identity=(0,))

    monkeypatch.setattr(namespace, "_observe_scratch_filesystem", changed)
    summary = root.recover_abandoned()
    assert not summary.complete
    assert summary.removed == 0
    assert parent.ticket.path.is_dir()


@pytest.mark.skipif(sys.platform != "darwin", reason="Darwin ACL proof")
def test_darwin_deny_only_acl_does_not_block_private_directory(tmp_path: Path) -> None:
    base = tmp_path.resolve()
    root = _open_namespace(base, base)
    result = subprocess.run(
        ["chmod", "+a", "everyone deny delete", str(root.ticket.path)],
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    try:
        assert _open_namespace(base, base).ticket == root.ticket
    finally:
        subprocess.run(
            ["chmod", "-N", str(root.ticket.path)],
            capture_output=True,
            timeout=15,
            check=True,
        )


def test_darwin_acl_inspection_failure_is_uncertainty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from recon_core.adapters import _scratch_namespace as namespace

    def unavailable(path: Path, info: os.stat_result) -> bool:
        raise AttributeError("PRIVATE_SENTINEL")

    monkeypatch.setattr(namespace, "_darwin_no_acl_grants_native", unavailable)
    assert not namespace._darwin_no_acl_grants(tmp_path, tmp_path.stat())


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.skipif(sys.platform != "win32", reason="Windows native file ACL proof")
@pytest.mark.parametrize("name", ["owner", "root.lock"])
def test_windows_broadened_root_file_refuses_reopen(tmp_path: Path, name: str) -> None:
    base = tmp_path.resolve()
    root = _open_namespace(base, base)
    file = root.ticket.path / name
    original = file.read_bytes()
    result = subprocess.run(
        ["icacls", str(file), "/grant", "*S-1-1-0:R"],
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    with pytest.raises(_NamespaceError):
        _open_namespace(base, base)
    assert file.read_bytes() == original


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.skipif(sys.platform != "win32", reason="Windows native file ACL proof")
@pytest.mark.parametrize("name", ["owner", "parent.lock", "worker.lock", "spill/fixture.tmp"])
def test_windows_broadened_session_file_is_retained(tmp_path: Path, name: str) -> None:
    from recon_core.adapters._resource_scratch import _Recovery

    base = tmp_path.resolve()
    root = _open_namespace(base, base)
    parent = root.create_session()
    ticket = parent.ticket
    spill = ticket.path / "spill" / "fixture.tmp"
    spill.write_bytes(b"synthetic")
    parent.release()
    result = subprocess.run(
        ["icacls", str(ticket.path / name), "/grant", "*S-1-1-0:R"],
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    assert root.recover(ticket) is _Recovery.RETAINED
    assert root.recover_abandoned().retained == 1
    assert spill.read_bytes() == b"synthetic"
    assert (ticket.path / "owner").is_file()


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.skipif(sys.platform != "win32", reason="Windows opened file ACL proof")
def test_windows_file_acl_checks_actual_open_handle(tmp_path: Path) -> None:
    from recon_core.adapters._windows_scratch_security import (
        _verify_private_file,
        _WindowsScratchSecurityError,
    )

    base = tmp_path.resolve()
    root = _open_namespace(base, base)
    first = root.ticket.path / "owner"
    second = root.ticket.path / "root.lock"
    with first.open("rb") as stream:
        _verify_private_file(first, fd=stream.fileno())
        with pytest.raises(_WindowsScratchSecurityError):
            _verify_private_file(second, fd=stream.fileno())


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.skipif(sys.platform != "win32", reason="Windows ancestor ACL proof")
@pytest.mark.parametrize("ancestor", ["base", "parent"])
def test_windows_unsafe_ancestor_refuses_namespace_creation(tmp_path: Path, ancestor: str) -> None:
    parent = tmp_path.resolve() / "parent"
    parent.mkdir()
    base = parent / "base"
    base.mkdir()
    path = _namespace_path(base, base)
    affected = base if ancestor == "base" else parent
    subprocess.run(
        ["icacls", str(affected), "/grant", "*S-1-1-0:(DC)"],
        capture_output=True,
        timeout=15,
        check=True,
    )
    with pytest.raises(_NamespaceError):
        _open_namespace(base, base)
    assert not path.exists()


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.skipif(sys.platform != "win32", reason="Windows ancestor ACL proof")
@pytest.mark.parametrize("ancestor", ["base", "parent"])
def test_windows_changed_ancestor_retains_existing_storage(tmp_path: Path, ancestor: str) -> None:
    from recon_core.adapters._resource_scratch import _Recovery, _ScratchError

    parent = tmp_path.resolve() / "parent"
    parent.mkdir()
    base = parent / "base"
    base.mkdir()
    root = _open_namespace(base, base)
    session = root.create_session()
    session.release()
    fixture = session.ticket.path / "spill" / "fixture.tmp"
    fixture.write_bytes(b"synthetic")
    affected = base if ancestor == "base" else parent
    subprocess.run(
        ["icacls", str(affected), "/grant", "*S-1-1-0:(DC)"],
        capture_output=True,
        timeout=15,
        check=True,
    )
    with pytest.raises(_NamespaceError):
        _open_namespace(base, base)
    with pytest.raises(_ScratchError):
        root.create_session()
    assert root.recover(session.ticket) is _Recovery.RETAINED
    summary = root.recover_abandoned()
    assert not summary.complete and summary.removed == 0
    assert fixture.read_bytes() == b"synthetic"


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.skipif(sys.platform != "win32", reason="Windows ancestor ACL proof")
def test_windows_shared_read_and_add_directory_ancestor_remains_usable(tmp_path: Path) -> None:
    from recon_core.adapters._resource_scratch import _Recovery

    base = tmp_path.resolve() / "base"
    base.mkdir()
    for grant in ("RX", "(AD)"):
        subprocess.run(
            ["icacls", str(base), "/grant", f"*S-1-1-0:{grant}"],
            capture_output=True,
            timeout=15,
            check=True,
        )
    root = _open_namespace(base, base)
    session = root.create_session()
    session.release()
    assert _open_namespace(base, base).ticket == root.ticket
    assert root.recover(session.ticket) is _Recovery.REMOVED
