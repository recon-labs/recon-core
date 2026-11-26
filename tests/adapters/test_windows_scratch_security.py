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


@pytest.mark.regression_capture("windows-scratch-private-acl")
def test_native_private_file_inheritance_and_explicit_acl(tmp_path: Path) -> None:
    from recon_core.adapters._windows_scratch_security import _verify_private_file

    root = tmp_path.resolve() / "private"
    _create_private_directory(root)
    file = root / "fixture"
    file.write_bytes(b"synthetic")
    _verify_private_file(file)
    result = subprocess.run(
        ["icacls", str(file), "/inheritance:d"],
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    _verify_private_file(file)
    with pytest.raises(_WindowsScratchSecurityError):
        _verify_private_file(root)
    with pytest.raises(_WindowsScratchSecurityError):
        _verify_private_directory(file)


@pytest.mark.regression_capture("windows-scratch-private-acl")
def test_native_file_acl_broadening_is_rejected(tmp_path: Path) -> None:
    from recon_core.adapters._windows_scratch_security import _verify_private_file

    root = tmp_path.resolve() / "private"
    _create_private_directory(root)
    file = root / "fixture"
    file.write_bytes(b"synthetic")
    _verify_private_file(file)
    result = subprocess.run(
        ["icacls", str(file), "/grant", "*S-1-1-0:R"],
        capture_output=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0
    # A verified parent directory alone is not proof of file privacy.
    _verify_private_directory(root)
    with pytest.raises(_WindowsScratchSecurityError):
        _verify_private_file(file)
    assert file.read_bytes() == b"synthetic"


@pytest.mark.regression_capture("windows-scratch-private-acl")
def test_native_file_owner_boundary() -> None:
    import ctypes as ct
    from ctypes import wintypes as wt

    from recon_core.adapters._windows_scratch_security import (
        _api,
        _libraries,
        _process_user,
        _trusted_owner,
    )

    kernel, security = _libraries()
    convert = _api(security, "ConvertStringSidToSidW", wt.BOOL, wt.LPCWSTR, ct.POINTER(ct.c_void_p))
    free = _api(kernel, "LocalFree", ct.c_void_p, ct.c_void_p)
    with _process_user(kernel, security) as (user, _):
        assert _trusted_owner(security, user, user, directory=True)
        assert _trusted_owner(security, user, user, directory=False)
        for value, allowed in (("S-1-5-32-544", True), ("S-1-1-0", False), ("S-1-5-32-545", False)):
            owner = ct.c_void_p()
            assert convert(value, ct.byref(owner))
            try:
                assert not _trusted_owner(security, owner, user, directory=True)
                assert _trusted_owner(security, owner, user, directory=False) is allowed
            finally:
                free(owner)


@pytest.mark.regression_capture("windows-scratch-private-acl")
@pytest.mark.parametrize("directory", [True, False])
def test_native_security_handle_must_match_requested_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory: bool
) -> None:
    from typing import Any

    from recon_core.adapters import _windows_scratch_security as native

    root = tmp_path.resolve() / "private"
    _create_private_directory(root)
    expected, substitute = root / "expected", root / "substitute"
    if directory:
        _create_private_directory(expected)
        _create_private_directory(substitute)
        verify = native._verify_private_directory
    else:
        expected.write_bytes(b"expected")
        substitute.write_bytes(b"substitute")
        verify = native._verify_private_file
    verify(expected)
    verify(substitute)
    original = native._api
    redirected = False

    def api(library: Any, name: str, result: Any, *args: Any) -> Any:
        function = original(library, name, result, *args)
        if name != "CreateFileW":
            return function

        def open_file(path: str, *values: Any) -> Any:
            nonlocal redirected
            if not redirected and path == str(expected):
                redirected = True
                return function(str(substitute), *values)
            return function(path, *values)

        return open_file

    with monkeypatch.context() as context:
        context.setattr(native, "_api", api)
        with pytest.raises(_WindowsScratchSecurityError):
            verify(expected)
        assert redirected
    verify(expected)
    verify(substitute)
