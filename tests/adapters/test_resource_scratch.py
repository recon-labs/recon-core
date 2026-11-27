"""Current-check private scratch creation, isolation and confirmed cleanup."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from recon_core.adapters._resource_scratch import _ScratchError


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
def test_check_scratch_abrupt_exit_leaves_residue_without_blocking_next_check(
    tmp_path: Path,
) -> None:
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
    from recon_core.adapters._darwin_scratch_security import _darwin_no_acl_grants

    base = tmp_path.resolve() / "acl-parent"
    base.mkdir(mode=0o700)
    subprocess.run(
        ["chmod", "+a", "everyone allow list,search,file_inherit,directory_inherit", str(base)],
        capture_output=True,
        timeout=15,
        check=True,
    )
    inherited = base / "inherited-control"
    inherited.mkdir(mode=0o700)
    assert not _darwin_no_acl_grants(inherited, inherited.lstat())
    inherited.rmdir()
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


@pytest.mark.regression_capture("scratch-namespace-qualification")
def test_darwin_acl_inspection_failure_is_uncertainty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from recon_core.adapters import _darwin_scratch_security as security

    def unavailable(path: Path, info: os.stat_result) -> bool:
        raise AttributeError("PRIVATE_SENTINEL")

    monkeypatch.setattr(security, "_darwin_no_acl_grants_native", unavailable)
    assert not security._darwin_no_acl_grants(tmp_path, tmp_path.stat())


@pytest.mark.regression_capture("owned-scratch-untrusted-retained")
@pytest.mark.skipif(os.name != "posix", reason="POSIX private directory mode")
def test_check_scratch_retains_storage_when_privacy_changes(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch

    scratch = _resource_scratch._create_check_scratch(tmp_path.resolve())
    data = scratch.path / "fixture.tmp"
    data.write_bytes(b"retain")
    scratch.path.chmod(0o755)
    try:
        with pytest.raises(_ScratchError):
            scratch.cleanup(native_closed=True)
        assert data.read_bytes() == b"retain"
    finally:
        scratch.path.chmod(0o700)
        scratch.cleanup(native_closed=True)


@pytest.mark.regression_capture("scratch-namespace-qualification")
@pytest.mark.skipif(sys.platform != "win32", reason="Windows native base ACL")
def test_check_scratch_windows_base_permissions(tmp_path: Path) -> None:
    from recon_core.adapters import _resource_scratch

    base = tmp_path.resolve() / "base"
    base.mkdir()
    for grant in ("RX", "(AD)"):
        subprocess.run(
            ["icacls", str(base), "/grant", f"*S-1-1-0:{grant}"],
            capture_output=True,
            timeout=15,
            check=True,
        )
    scratch = _resource_scratch._create_check_scratch(base)
    data = scratch.path / "fixture.tmp"
    data.write_bytes(b"retain")
    subprocess.run(
        ["icacls", str(base), "/grant", "*S-1-1-0:(DC)"],
        capture_output=True,
        timeout=15,
        check=True,
    )
    with pytest.raises(_ScratchError):
        _resource_scratch._create_check_scratch(base)
    with pytest.raises(_ScratchError):
        scratch.cleanup(native_closed=True)
    assert data.read_bytes() == b"retain"
