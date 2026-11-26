"""Private Windows scratch ACL provider.

Use an explicit protected owner-only inheritable DACL at creation, then
inspect the actual descriptor through an existing object handle. This
is cooperative local-user privacy, not protection from privileged actors
or a proof of filesystem locking semantics.
"""

import ctypes as ct
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from ctypes import wintypes as wt
from importlib import import_module
from pathlib import Path
from typing import Any


class _WindowsScratchSecurityError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Windows scratch privacy could not be verified.")


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
        security,
        "GetTokenInformation",
        wt.BOOL,
        wt.HANDLE,
        ct.c_int,
        ct.c_void_p,
        wt.DWORD,
        ct.POINTER(wt.DWORD),
    )
    to_string = _api(
        security, "ConvertSidToStringSidW", wt.BOOL, ct.c_void_p, ct.POINTER(ct.c_void_p)
    )
    # File operations use the thread's effective security context. A process
    # SID is not proof when the current thread has an impersonation token;
    # an isolated worker does not automatically inherit that context.
    current_thread = _api(kernel, "GetCurrentThread", wt.HANDLE)
    open_thread_token = _api(
        security,
        "OpenThreadToken",
        wt.BOOL,
        wt.HANDLE,
        wt.DWORD,
        wt.BOOL,
        ct.POINTER(ct.c_void_p),
    )
    thread_token = ct.c_void_p()
    ctypes_module = import_module("ctypes")
    ctypes_module.set_last_error(0)
    if open_thread_token(current_thread(), 0x0008, True, ct.byref(thread_token)):
        close(thread_token)
        raise _WindowsScratchSecurityError()
    if ctypes_module.get_last_error() != 1008:  # ERROR_NO_TOKEN
        raise _WindowsScratchSecurityError()
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
            security,
            "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            wt.BOOL,
            wt.LPCWSTR,
            wt.DWORD,
            ct.POINTER(ct.c_void_p),
            ct.POINTER(wt.DWORD),
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


def _trusted_owner(
    security: Any, owner: ct.c_void_p, user: ct.c_void_p, *, directory: bool
) -> bool:
    """Accept only user ownership, or a privileged default leaf owner."""
    valid = _api(security, "IsValidSid", wt.BOOL, ct.c_void_p)
    equal = _api(security, "EqualSid", wt.BOOL, ct.c_void_p, ct.c_void_p)
    well_known = _api(security, "IsWellKnownSid", wt.BOOL, ct.c_void_p, ct.c_int)
    if not owner or not user or not valid(owner) or not valid(user):
        return False
    # Windows may assign newly created files to Builtin Administrators
    # rather than the token user. Privileged administrators are outside the
    # cooperative privacy boundary. Never accept an arbitrary group owner;
    # directories still require the exact user and the DACL is checked separately.
    return bool(equal(owner, user) or (not directory and well_known(owner, 26)))


def _ancestor_trusted_principal(
    security: Any, principal: ct.c_void_p, user: ct.c_void_p
) -> bool:
    valid = _api(security, "IsValidSid", wt.BOOL, ct.c_void_p)
    equal = _api(security, "EqualSid", wt.BOOL, ct.c_void_p, ct.c_void_p)
    well_known = _api(security, "IsWellKnownSid", wt.BOOL, ct.c_void_p, ct.c_int)
    return bool(
        principal
        and valid(principal)
        and (equal(principal, user) or well_known(principal, 22) or well_known(principal, 26))
    )


def _verify_descriptor(
    security: Any,
    handle: Any,
    sid: ct.c_void_p,
    kernel: Any,
    *,
    directory: bool,
    ancestor: bool = False,
) -> None:
    get_info = _api(
        security,
        "GetSecurityInfo",
        wt.DWORD,
        wt.HANDLE,
        ct.c_int,
        wt.DWORD,
        ct.POINTER(ct.c_void_p),
        ct.c_void_p,
        ct.POINTER(ct.c_void_p),
        ct.c_void_p,
        ct.POINTER(ct.c_void_p),
    )
    local_free = _api(kernel, "LocalFree", ct.c_void_p, ct.c_void_p)
    equal = _api(security, "EqualSid", wt.BOOL, ct.c_void_p, ct.c_void_p)
    control = _api(
        security,
        "GetSecurityDescriptorControl",
        wt.BOOL,
        ct.c_void_p,
        ct.POINTER(ct.c_ushort),
        ct.POINTER(wt.DWORD),
    )
    valid_acl = _api(security, "IsValidAcl", wt.BOOL, ct.c_void_p)
    acl_info = _api(
        security, "GetAclInformation", wt.BOOL, ct.c_void_p, ct.c_void_p, wt.DWORD, ct.c_int
    )
    get_ace = _api(security, "GetAce", wt.BOOL, ct.c_void_p, wt.DWORD, ct.POINTER(ct.c_void_p))
    valid_sid = _api(security, "IsValidSid", wt.BOOL, ct.c_void_p)
    sid_length = _api(security, "GetLengthSid", wt.DWORD, ct.c_void_p)
    owner = ct.c_void_p()
    dacl = ct.c_void_p()
    descriptor = ct.c_void_p()
    try:
        if (
            get_info(
                handle, 1, 5, ct.byref(owner), None, ct.byref(dacl), None, ct.byref(descriptor)
            )
            != 0
        ):
            raise _WindowsScratchSecurityError()
        flags, revision = ct.c_ushort(), wt.DWORD()
        size = _AclSize()
        if (
            not owner
            or not dacl
            or not descriptor
            or not (
                _ancestor_trusted_principal(security, owner, sid)
                if ancestor
                else _trusted_owner(security, owner, sid, directory=directory)
            )
            or not control(descriptor, ct.byref(flags), ct.byref(revision))
            or not flags.value & 4  # SE_DACL_PRESENT
            or (directory and not ancestor and not flags.value & 0x1000)  # SE_DACL_PROTECTED
            or not valid_acl(dacl)
            or not acl_info(dacl, ct.byref(size), ct.sizeof(size), 2)
            or (not ancestor and size.count != 1)
        ):
            raise _WindowsScratchSecurityError()
        for index in range(size.count):
            raw = ct.c_void_p()
            if not get_ace(dacl, index, ct.byref(raw)) or not raw.value:
                raise _WindowsScratchSecurityError()
            ace = _Ace.from_address(raw.value)
            if (
                ace.kind not in (0, 1)
                or ace.size < ct.sizeof(_Ace) + 8
                or ace.size > size.used
            ):
                raise _WindowsScratchSecurityError()
            trustee = ct.c_void_p(raw.value + ct.sizeof(_Ace))
            if not valid_sid(trustee) or ace.size != ct.sizeof(_Ace) + sid_length(trustee):
                raise _WindowsScratchSecurityError()
            if ancestor:
                # Simple deny entries cannot grant path control. Inherit-only
                # entries do not apply to this directory; descendants are
                # checked independently. Unknown ACE types/flags stay unknown.
                if ace.flags & ~0x1F:
                    raise _WindowsScratchSecurityError()
                if ace.kind == 1 or ace.flags & 8:
                    continue
                # Untrusted effective grants may list, traverse, read and add
                # subdirectories, but must not permit deleting/renaming,
                # changing security, or writing reparse-relevant attributes.
                # A positive allowlist also rejects unresolved generic rights.
                safe = 0x001200AD  # SYNCHRONIZE, READ_CONTROL, RA, X, REA, AD, RD
                if ace.mask & ~safe and not _ancestor_trusted_principal(security, trustee, sid):
                    raise _WindowsScratchSecurityError()
            else:
                # Exact private owner grant; directories propagate to children.
                allowed_flags = (3,) if directory else (0, 0x10)
                if (
                    ace.kind != 0
                    or ace.flags not in allowed_flags
                    or ace.mask != 0x001F01FF
                    or not equal(trustee, sid)
                ):
                    raise _WindowsScratchSecurityError()
    finally:
        if descriptor:
            local_free(descriptor)


class _FileIdInfo(ct.Structure):
    _fields_ = [("volume", ct.c_uint64), ("identifier", ct.c_ubyte * 16)]


class _FileStandardInfo(ct.Structure):
    _fields_ = [
        ("allocation", ct.c_int64),
        ("size", ct.c_int64),
        ("links", wt.DWORD),
        ("delete_pending", ct.c_ubyte),
        ("directory", ct.c_ubyte),
    ]


class _FileAttributeTagInfo(ct.Structure):
    _fields_ = [("attributes", wt.DWORD), ("tag", wt.DWORD)]


def _native_object_identity(kernel: Any, handle: Any, *, directory: bool) -> tuple[int, bytes]:
    """Read native identity and object shape, not a translated path or stat ID."""
    query = _api(
        kernel,
        "GetFileInformationByHandleEx",
        wt.BOOL,
        wt.HANDLE,
        ct.c_int,
        ct.c_void_p,
        wt.DWORD,
    )
    identity = _FileIdInfo()
    standard = _FileStandardInfo()
    attributes = _FileAttributeTagInfo()
    if (
        not query(handle, 18, ct.byref(identity), ct.sizeof(identity))
        or not query(handle, 1, ct.byref(standard), ct.sizeof(standard))
        or not query(handle, 9, ct.byref(attributes), ct.sizeof(attributes))
        or not any(identity.identifier)
        or bool(standard.directory) != directory
        or standard.delete_pending
        or (not directory and standard.links != 1)
        or attributes.attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise _WindowsScratchSecurityError()
    return identity.volume, bytes(identity.identifier)


@contextmanager
def _open_security_handle(kernel: Any, path: Path) -> Iterator[Any]:
    open_file = _api(
        kernel,
        "CreateFileW",
        wt.HANDLE,
        wt.LPCWSTR,
        wt.DWORD,
        wt.DWORD,
        ct.c_void_p,
        wt.DWORD,
        wt.DWORD,
        wt.HANDLE,
    )
    close = _api(kernel, "CloseHandle", wt.BOOL, wt.HANDLE)
    # READ_CONTROL | FILE_READ_ATTRIBUTES, share read/write (not delete),
    # OPEN_EXISTING, BACKUP_SEMANTICS | OPEN_REPARSE_POINT.
    handle = open_file(str(path), 0x20080, 3, None, 3, 0x02200000, None)
    if handle in (None, ct.c_void_p(-1).value):
        raise _WindowsScratchSecurityError()
    try:
        yield handle
    finally:
        close(handle)


def _confirm_native_identity(kernel: Any, path: Path, handle: Any, *, directory: bool) -> None:
    identity = _native_object_identity(kernel, handle, directory=directory)
    # Independently reopen while the inspected object remains held. The native
    # volume and full file ID must agree, even if path stat observations agree.
    with _open_security_handle(kernel, path) as named:
        if (
            _native_object_identity(kernel, named, directory=directory) != identity
            or _native_object_identity(kernel, handle, directory=directory) != identity
        ):
            raise _WindowsScratchSecurityError()


def _verify_private_directory(path: Path) -> None:
    """Verify actual owner, protected DACL and inheritable grant."""
    _verify_private_object(path, directory=True)


def _verify_private_file(path: Path, *, fd: int | None = None) -> None:
    """Verify the actual leaf, using the operation's handle when supplied."""
    if fd is None:
        _verify_private_object(path, directory=False)
        return
    try:
        before = path.lstat()
        if (
            not path.is_absolute()
            or path.resolve(strict=True) != path
            or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or getattr(before, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise _WindowsScratchSecurityError()

        def matches(info: os.stat_result) -> bool:
            return (
                info.st_dev == before.st_dev
                and info.st_ino == before.st_ino
                and info.st_ino > 0
                and info.st_nlink == 1
                and stat.S_ISREG(info.st_mode)
                and not getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            )

        if not matches(os.fstat(fd)):
            raise _WindowsScratchSecurityError()
        kernel, security = _libraries()
        handle = import_module("msvcrt").get_osfhandle(fd)
        _confirm_native_identity(kernel, path, handle, directory=False)
        with _process_user(kernel, security) as (sid, _):
            _verify_descriptor(security, handle, sid, kernel, directory=False)
        _confirm_native_identity(kernel, path, handle, directory=False)
        if not matches(os.fstat(fd)) or not matches(path.lstat()):
            raise _WindowsScratchSecurityError()
    except Exception:
        raise _WindowsScratchSecurityError() from None


def _verify_ancestor_directory(path: Path) -> None:
    """Verify an existing ancestor without requiring owner-only read access."""
    _verify_private_object(path, directory=True, ancestor=True)


def _verify_private_object(path: Path, *, directory: bool, ancestor: bool = False) -> None:
    try:
        before = path.lstat()
        if (
            not path.is_absolute()
            or path.resolve(strict=True) != path
            or not (stat.S_ISDIR(before.st_mode) if directory else stat.S_ISREG(before.st_mode))
            or (not directory and before.st_nlink != 1)
            or getattr(before, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise _WindowsScratchSecurityError()
        kernel, security = _libraries()
        with _open_security_handle(kernel, path) as handle:
            _confirm_native_identity(kernel, path, handle, directory=directory)
            with _process_user(kernel, security) as (sid, _):
                _verify_descriptor(
                    security, handle, sid, kernel, directory=directory, ancestor=ancestor
                )
            _confirm_native_identity(kernel, path, handle, directory=directory)
            after = path.lstat()
            if (
                (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                or getattr(after, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                or (not directory and after.st_nlink != 1)
            ):
                raise _WindowsScratchSecurityError()
    except Exception:
        raise _WindowsScratchSecurityError() from None
