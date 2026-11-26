"""Portable observation facts are partial and never an enforcement claim."""

import subprocess
import sys
import textwrap
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import SimpleNamespace

import pytest

from recon_core.adapters._portable_resource_observation import (
    _classify_mounted_filesystem,
    _finite_rlimit,
    _observe_portable_resources,
    _PortableFacts,
    _read_portable_facts,
    _windows_drive_kind,
    _WindowsScope,
)


def _provider(*, memory: object = 1024, affinity: object = (0, 2)):
    process = SimpleNamespace(
        memory_info=lambda: SimpleNamespace(rss=100, vms=200, private=120),
        cpu_affinity=lambda: affinity,
    )
    return SimpleNamespace(
        virtual_memory=lambda: SimpleNamespace(available=memory),
        Process=lambda: process,
        disk_partitions=lambda **kwargs: [
            SimpleNamespace(mountpoint="/", fstype="apfs"),
            SimpleNamespace(mountpoint="/Volumes/ram", fstype="tmpfs"),
        ],
    )


@pytest.mark.regression_capture("portable-resource-observation-uncertainty")
def test_portable_facts_preserve_available_memory_and_affinity() -> None:
    facts = _read_portable_facts(_provider(), "darwin", PurePosixPath("/private/tmp"))
    assert facts.host_available_bytes == 1024
    assert facts.affinity_count == 2
    assert facts.process_rss_bytes == 100
    assert facts.process_virtual_bytes == 200
    assert facts.process_private_commit_bytes is None
    assert facts.scratch_memory_backed is False
    assert not facts.scope_complete


@pytest.mark.parametrize("value", [None, True, -1, 1.0, "1024"])
def test_invalid_host_observation_is_unknown(value: object) -> None:
    facts = _read_portable_facts(_provider(memory=value), "darwin", PurePosixPath("/tmp"))
    assert facts.host_available_bytes is None
    assert facts.process_rss_bytes == 100


def test_zero_memory_is_not_unknown() -> None:
    facts = _read_portable_facts(_provider(memory=0), "darwin", PurePosixPath("/tmp"))
    assert facts.host_available_bytes == 0


def test_affinity_unavailable_does_not_erase_memory() -> None:
    provider = _provider()

    def denied():
        raise PermissionError("PRIVATE_SENTINEL")

    provider.Process().cpu_affinity = denied
    facts = _read_portable_facts(provider, "darwin", PurePosixPath("/tmp"))
    assert facts.affinity_count is None
    assert facts.host_available_bytes == 1024
    assert "PRIVATE_SENTINEL" not in repr(facts)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (PurePosixPath("/Volumes/ram/tmp"), True),
        (PurePosixPath("/Volumes/ram-other/tmp"), False),
        (PurePosixPath("/Volumes/net/tmp"), None),
    ],
)
def test_most_specific_mount_kind(path: PurePosixPath, expected: bool | None) -> None:
    assert (
        _classify_mounted_filesystem(
            path, (("/", "apfs"), ("/Volumes/ram", "tmpfs"), ("/Volumes/net", "smbfs"))
        )
        is expected
    )


def test_conflicting_mount_evidence_is_unknown() -> None:
    assert (
        _classify_mounted_filesystem(
            PurePosixPath("/scratch/tmp"), (("/scratch", "apfs"), ("/scratch", "tmpfs"))
        )
        is None
    )


@pytest.mark.parametrize(
    ("kind", "expected"),
    [(0, None), (1, None), (2, False), (3, False), (4, None), (5, None), (6, True), (7, None)],
)
def test_windows_drive_kind(kind: int, expected: bool | None) -> None:
    assert _windows_drive_kind(kind) is expected


@pytest.mark.regression_capture("portable-resource-observation-uncertainty")
def test_windows_job_observation_is_not_host_memory_proof() -> None:
    facts = _read_portable_facts(
        _provider(),
        "win32",
        PureWindowsPath("C:/temp"),
        windows_scope=_WindowsScope(
            in_job=True,
            processor_group_count=2,
            process_commit_limit_bytes=1000,
            job_commit_limit_bytes=2000,
        ),
        windows_drive=3,
    )
    assert facts.host_available_bytes == 1024
    assert facts.process_private_commit_bytes == 120
    assert facts.process_virtual_bytes is None
    assert facts.windows_scope is not None
    assert facts.windows_scope.process_commit_limit_bytes == 1000
    assert facts.windows_scope.job_commit_limit_bytes == 2000
    assert facts.process_commit_headroom_bytes == 880
    assert facts.affinity_count is None
    assert not facts.scope_complete


def test_missing_provider_is_partial(tmp_path: Path) -> None:
    facts = _observe_portable_resources(tmp_path, "darwin", loader=lambda: None)
    assert facts == _PortableFacts()


def test_real_optional_portable_observation(tmp_path: Path) -> None:
    pytest.importorskip("psutil")
    facts = _observe_portable_resources(tmp_path, sys.platform)
    assert facts.host_available_bytes is not None
    assert facts.host_available_bytes >= 0
    assert facts.process_rss_bytes is not None
    assert facts.process_rss_bytes > 0
    assert not facts.scope_complete
    assert not list(tmp_path.iterdir())


def test_missing_scratch_does_not_erase_host_facts() -> None:
    facts = _read_portable_facts(_provider(), "darwin", None)
    assert facts.host_available_bytes == 1024
    assert facts.scratch_memory_backed is None


def test_macos_unlimited_process_limit_is_not_finite() -> None:
    resource = SimpleNamespace(
        RLIM_INFINITY=(1 << 63) - 1,
        RLIMIT_AS=1,
        RLIMIT_DATA=2,
        getrlimit=lambda name: ((1 << 63) - 1, 0) if name == 1 else (1000, 2000),
    )
    assert _finite_rlimit(resource, "RLIMIT_AS") is None
    assert _finite_rlimit(resource, "RLIMIT_DATA") == 1000


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job API")
def test_windows_actual_immediate_job_limits() -> None:
    pytest.importorskip("psutil")
    code = textwrap.dedent(
        """
        import ctypes
        import sys
        from pathlib import Path
        from recon_core.adapters._portable_resource_observation import (
            _ExtendedJobLimits, _observe_portable_resources
        )
        k = ctypes.WinDLL("kernel32")
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        k.CreateJobObjectW.restype = ctypes.c_void_p
        job = k.CreateJobObjectW(None, None)
        assert job
        k.CloseHandle.argtypes = [ctypes.c_void_p]
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        k.SetInformationJobObject.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32
        ]
        try:
            limits = _ExtendedJobLimits()
            limits.basic.flags = 0x100 | 0x200
            limits.process_limit = 512 * 1024**2
            limits.job_limit = 768 * 1024**2
            assert k.SetInformationJobObject(
                job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
            )
            if not k.AssignProcessToJobObject(job, k.GetCurrentProcess()):
                sys.exit(77)
            facts = _observe_portable_resources(Path.cwd(), sys.platform)
            scope = facts.windows_scope
            assert scope is not None and scope.in_job is True
            assert scope.process_commit_limit_bytes == limits.process_limit
            assert scope.job_commit_limit_bytes == limits.job_limit
            assert facts.process_commit_headroom_bytes is not None
            assert 0 < facts.process_commit_headroom_bytes < limits.process_limit
            assert not facts.scope_complete
        finally:
            k.CloseHandle(job)
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30, check=False
    )
    if result.returncode == 77:
        pytest.skip("Runner does not allow nested job assignment")
    assert result.returncode == 0, result.stderr
