"""Actual Windows private ACL creation and verification on synthetic storage."""

import subprocess
import sys
from pathlib import Path

import pytest

from recon_core.adapters._windows_scratch_security import (
    _create_private_directory,
    _verify_private_directory,
    _WindowsScratchSecurityError,
)

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows native ACL proof")


@pytest.mark.regression_capture("windows-scratch-private-acl")
def test_native_private_directory_creation(tmp_path: Path) -> None:
    root = tmp_path.resolve() / "private directory"
    _create_private_directory(root)
    _verify_private_directory(root)
    with pytest.raises(FileExistsError):
        _create_private_directory(root)
    child = root / "child"
    _create_private_directory(child)
    _verify_private_directory(child)
    (child / "fixture").write_bytes(b"synthetic")
    assert (child / "fixture").read_bytes() == b"synthetic"


@pytest.mark.regression_capture("windows-scratch-private-acl")
def test_native_acl_broadening_is_rejected(tmp_path: Path) -> None:
    root = tmp_path.resolve() / "private"
    _create_private_directory(root)
    _verify_private_directory(root)
    # Use the well-known Everyone SID, not a localized account name.
    result = subprocess.run(
        ["icacls", str(root), "/grant", "*S-1-1-0:(OI)(CI)RX"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, "Could not broaden synthetic test ACL."
    with pytest.raises(_WindowsScratchSecurityError):
        _verify_private_directory(root)
    assert root.is_dir()


def test_native_acl_inheritance_is_not_protection(tmp_path: Path) -> None:
    root = tmp_path.resolve() / "private"
    _create_private_directory(root)
    inherited = root / "inherited"
    inherited.mkdir()
    with pytest.raises(_WindowsScratchSecurityError):
        _verify_private_directory(inherited)


@pytest.mark.regression_capture("windows-scratch-private-acl")
def test_native_impersonation_cannot_authorize_process_namespace(tmp_path: Path) -> None:
    from ctypes import wintypes as wt

    from recon_core.adapters._windows_scratch_security import _api, _libraries

    root = tmp_path.resolve() / "private"
    _create_private_directory(root)
    _, security = _libraries()
    impersonate = _api(security, "ImpersonateSelf", wt.BOOL, wt.DWORD)
    revert = _api(security, "RevertToSelf", wt.BOOL)
    candidate = tmp_path.resolve() / "impersonated"
    assert impersonate(2), "Could not establish native thread impersonation."
    try:
        with pytest.raises(_WindowsScratchSecurityError):
            _create_private_directory(candidate)
        with pytest.raises(_WindowsScratchSecurityError):
            _verify_private_directory(root)
        assert not candidate.exists()
    finally:
        assert revert(), "Could not restore native process security context."
    _verify_private_directory(root)
    _create_private_directory(candidate)
    _verify_private_directory(candidate)
