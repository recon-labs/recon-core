"""Private Windows directory ACL provider.

Use an explicit protected owner-only inheritable DACL at creation, then
inspect the actual descriptor through an existing directory handle. This
is cooperative local-user privacy, not protection from privileged actors
or a proof of filesystem locking semantics.
"""

import ctypes as ct
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from ctypes import wintypes as wt
from importlib import import_module
from pathlib import Path
from typing import Any


class _WindowsScratchSecurityError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Windows scratch directory privacy could not be verified.")


class _SecurityAttributes(ct.Structure):
    _fields_ = [
        ("length", wt.DWORD),
        ("descriptor", ct.c_void_p),
        ("inherit", wt.BOOL),
    ]


class _AclSize(ct.Structure):
    _fields_ = [
        ("count", wt.DWORD),
        ("used", wt.DWORD),
        ("free", wt.DWORD),
    ]


class _Ace(ct.Structure):
    _fields_ = [
        ("kind", ct.c_ubyte),
        ("flags", ct.c_ubyte),
        ("size", ct.c_ushort),
        ("mask", wt.DWORD),
    ]


def _api(library: Any, name: str, result: Any, *args: Any) -> Any:
    function = getattr(library, name)
    function.argtypes = list(args)
    function.restype = result
    return function


def _libraries() -> tuple[Any, Any]:
    loader = import_module("ctypes").WinDLL
    return loader("kernel32", use_last_error=True), loader("advapi32", use_last_error=True)


@contextmanager
def _process_user(kernel: Any, security: Any) -> Iterator[tuple[ct.c_void_p, str]]:
    handle = ct.c_void_p()
    current = _api(kernel, "GetCurrentProcess", wt.HANDLE)
    close = _api(kernel, "CloseHandle", wt.BOOL, wt.HANDLE)
    local_free = _api(kernel, "LocalFree", ct.c_void_p, ct.c_void_p)
    open_token = _api(
        security, "OpenProcessToken", wt.BOOL, wt.HANDLE, wt.DWORD, ct.POINTER(ct.c_void_p)
    )
    token_info = _api(
        security, "GetTokenInformation", wt.BOOL,
        wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD, ct.POINTER(wt.DWORD)
    )
    to_string = _api(
        security, "ConvertSidToStringSidW", wt.BOOL, ct.c_void_p, ct.POINTER(ct.c_void_p)
    )
    if not open_token(current(), 0x0008, ct.byref(handle)):
        raise _WindowsScratchSecurityError()
    try:
        needed = wt.DWORD()
        token_info(handle, 1, None, 0, ct.byref(needed))
        # TOKEN_USER is one SID_AND_ATTRIBUTES plus a SID (at most 68 bytes).
        # Allow alignment/padding but reject an unbounded native allocation.
        if not ct.sizeof(ct.c_void_p) <= needed.value <= 256:
            raise _WindowsScratchSecurityError()
        data = ct.create_string_buffer(needed.value)
        if not token_info(handle, 1, data, len(data), ct.byref(needed)):
            raise _WindowsScratchSecurityError()
        sid = ct.cast(data, ct.POINTER(ct.c_void_p))[0]
        if not sid:
            raise _WindowsScratchSecurityError()
        text = ct.c_void_p()
        if not to_string(sid, ct.byref(text)):
            raise _WindowsScratchSecurityError()
        try:
            yield ct.c_void_p(sid), ct.wstring_at(text)
        finally:
            local_free(text)
    finally:
        close(handle)


def _create_private_directory(path: Path) -> None:
    """Create, never adopt or repair, a directory with a protected DACL."""
    try:
        kernel, security = _libraries()
        local_free = _api(kernel, "LocalFree", ct.c_void_p, ct.c_void_p)
        convert = _api(
            security, "ConvertStringSecurityDescriptorToSecurityDescriptorW", wt.BOOL,
            wt.LPCWSTR, wt.DWORD, ct.POINTER(ct.c_void_p), ct.POINTER(wt.DWORD)
        )
        create = _api(
            kernel, "CreateDirectoryW", wt.BOOL, wt.LPCWSTR, ct.POINTER(_SecurityAttributes)
        )
        if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent:
            raise _WindowsScratchSecurityError()
        with _process_user(kernel, security) as (_, sid):
            descriptor = ct.c_void_p()
            # File/directory full access, object and container inheritance,
            # no inherited broader grants. Explicit owner is the process user.
            if not convert(f"O:{sid}D:P(A;OICI;FA;;;{sid})", 1, ct.byref(descriptor), None):
                raise _WindowsScratchSecurityError()
            try:
                attributes = _SecurityAttributes(ct.sizeof(_SecurityAttributes), descriptor, 0)
                if not create(str(path), ct.byref(attributes)):
                    if import_module("ctypes").get_last_error() in (80, 183):
                        raise FileExistsError("Private scratch directory already exists.")
                    raise _WindowsScratchSecurityError()
            finally:
                local_free(descriptor)
        _verify_private_directory(path)
    except FileExistsError:
        raise
    except Exception:
        raise _WindowsScratchSecurityError() from None


def _verify_descriptor(security: Any, handle: Any, sid: ct.c_void_p, kernel: Any) -> None:
    get_info = _api(
        security, "GetSecurityInfo", wt.DWORD, wt.HANDLE, ct.c_int, wt.DWORD,
        ct.POINTER(ct.c_void_p), ct.c_void_p, ct.POINTER(ct.c_void_p),
        ct.c_void_p, ct.POINTER(ct.c_void_p)
    )
    local_free = _api(kernel, "LocalFree", ct.c_void_p, ct.c_void_p)
    equal = _api(security, "EqualSid", wt.BOOL, ct.c_void_p, ct.c_void_p)
    control = _api(
        security, "GetSecurityDescriptorControl", wt.BOOL,
        ct.c_void_p, ct.POINTER(ct.c_ushort), ct.POINTER(wt.DWORD)
    )
    valid_acl = _api(security, "IsValidAcl", wt.BOOL, ct.c_void_p)
    acl_info = _api(
        security, "GetAclInformation", wt.BOOL,
        ct.c_void_p, ct.c_void_p, wt.DWORD, ct.c_int
    )
    get_ace = _api(
        security, "GetAce", wt.BOOL, ct.c_void_p, wt.DWORD, ct.POINTER(ct.c_void_p)
    )
    valid_sid = _api(security, "IsValidSid", wt.BOOL, ct.c_void_p)
    sid_length = _api(security, "GetLengthSid", wt.DWORD, ct.c_void_p)
    owner = ct.c_void_p()
    dacl = ct.c_void_p()
    descriptor = ct.c_void_p()
    try:
        if get_info(
            handle, 1, 5, ct.byref(owner), None, ct.byref(dacl), None, ct.byref(descriptor)
        ) != 0:
            raise _WindowsScratchSecurityError()
        flags, revision = ct.c_ushort(), wt.DWORD()
        size = _AclSize()
        if (
            not owner or not dacl or not descriptor
            or not equal(owner, sid)
            or not control(descriptor, ct.byref(flags), ct.byref(revision))
            or flags.value & 0x1004 != 0x1004
            or not valid_acl(dacl)
            or not acl_info(dacl, ct.byref(size), ct.sizeof(size), 2)
            or size.count != 1
        ):
            raise _WindowsScratchSecurityError()
        raw = ct.c_void_p()
        if not get_ace(dacl, 0, ct.byref(raw)) or not raw.value:
            raise _WindowsScratchSecurityError()
        ace = _Ace.from_address(raw.value)
        # ACCESS_ALLOWED_ACE with exactly OI|CI, not inherit-only, not
        # conditional/object-specific, and FILE_ALL_ACCESS.
        if (
            ace.kind != 0 or ace.flags != 3 or ace.mask != 0x001F01FF
            or ace.size < ct.sizeof(_Ace) + 8
            or ace.size > size.used
        ):
            raise _WindowsScratchSecurityError()
        trustee = ct.c_void_p(raw.value + ct.sizeof(_Ace))
        if (
            not valid_sid(trustee)
            or ace.size != ct.sizeof(_Ace) + sid_length(trustee)
            or not equal(trustee, sid)
        ):
            raise _WindowsScratchSecurityError()
    finally:
        if descriptor:
            local_free(descriptor)


def _verify_private_directory(path: Path) -> None:
    """Verify actual owner, protected DACL and inheritable grant."""
    try:
        before = path.lstat()
        if (
            not path.is_absolute() or path.resolve(strict=True) != path
            or not stat.S_ISDIR(before.st_mode)
            or before.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise _WindowsScratchSecurityError()
        kernel, security = _libraries()
        open_file = _api(
            kernel, "CreateFileW", wt.HANDLE, wt.LPCWSTR, wt.DWORD, wt.DWORD,
            ct.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE
        )
        close = _api(kernel, "CloseHandle", wt.BOOL, wt.HANDLE)
        # READ_CONTROL, share read/write (not delete), OPEN_EXISTING,
        # BACKUP_SEMANTICS | OPEN_REPARSE_POINT.
        handle = open_file(str(path), 0x20000, 3, None, 3, 0x02200000, None)
        if handle in (None, ct.c_void_p(-1).value):
            raise _WindowsScratchSecurityError()
        try:
            with _process_user(kernel, security) as (sid, _):
                _verify_descriptor(security, handle, sid, kernel)
            after = path.lstat()
            if (
                (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                or after.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise _WindowsScratchSecurityError()
        finally:
            close(handle)
    except Exception:
        raise _WindowsScratchSecurityError() from None
