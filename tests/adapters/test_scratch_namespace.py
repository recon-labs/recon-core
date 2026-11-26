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
