"""Portable observation facts are partial and never an enforcement claim."""

import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import SimpleNamespace

import pytest

from recon_core.adapters._portable_resource_observation import (
    _classify_mounted_filesystem,
    _observe_portable_resources,
    _PortableFacts,
    _read_portable_facts,
)


def _provider(*, memory: object = 1024, affinity: object = (0, 2)):
    process = SimpleNamespace(
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
    assert facts.scratch_memory_backed is False
    assert not facts.scope_complete


@pytest.mark.parametrize("value", [None, True, -1, 1.0, "1024"])
def test_invalid_host_observation_is_unknown(value: object) -> None:
    facts = _read_portable_facts(_provider(memory=value), "darwin", PurePosixPath("/tmp"))
    assert facts.host_available_bytes is None
    assert facts.affinity_count == 2


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


@pytest.mark.regression_capture("portable-resource-observation-uncertainty")
def test_windows_host_hints_are_not_complete_process_scope() -> None:
    facts = _read_portable_facts(_provider(), "win32", PureWindowsPath("C:/temp"))
    assert facts.host_available_bytes == 1024
    assert facts.affinity_count == 2
    assert facts.scratch_memory_backed is None
    assert not facts.scope_complete


def test_missing_provider_is_partial(tmp_path: Path) -> None:
    facts = _observe_portable_resources(tmp_path, "darwin", loader=lambda: None)
    assert facts == _PortableFacts()


def test_real_optional_portable_observation(tmp_path: Path) -> None:
    pytest.importorskip("psutil")
    facts = _observe_portable_resources(tmp_path, sys.platform)
    assert facts.host_available_bytes is not None
    assert facts.host_available_bytes >= 0
    assert not facts.scope_complete
    assert not list(tmp_path.iterdir())


def test_missing_scratch_does_not_erase_host_facts() -> None:
    facts = _read_portable_facts(_provider(), "darwin", None)
    assert facts.host_available_bytes == 1024
    assert facts.scratch_memory_backed is None


@pytest.mark.parametrize("platform", ["linux", "darwin", "win32", "future-platform"])
@pytest.mark.regression_capture("portable-resource-observation-uncertainty")
def test_portable_observation_does_not_require_process_memory_inspection(platform: str) -> None:
    calls: list[str] = []

    def memory_info():
        calls.append("memory_info")
        raise PermissionError("PRIVATE_SENTINEL")

    provider = SimpleNamespace(
        virtual_memory=lambda: SimpleNamespace(available=4096),
        Process=lambda: SimpleNamespace(memory_info=memory_info, cpu_affinity=lambda: [0, 2]),
        disk_partitions=lambda **kwargs: [],
    )
    facts = _read_portable_facts(provider, platform, None)

    assert facts.host_available_bytes == 4096
    assert not facts.scope_complete
    assert not calls
    assert "PRIVATE_SENTINEL" not in repr(facts)


@pytest.mark.parametrize("platform", ["win32", "darwin"])
@pytest.mark.regression_capture("portable-resource-observation-uncertainty")
def test_portable_observation_does_not_probe_os_job_or_rlimit_apis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    from recon_core.adapters import _portable_resource_observation as observation

    seen: list[str] = []

    def unexpected_import(name: str):
        seen.append(name)
        raise ImportError("PRIVATE_SENTINEL")

    monkeypatch.setattr(observation, "import_module", unexpected_import)
    facts = _observe_portable_resources(tmp_path, platform, loader=_provider)

    assert facts.host_available_bytes == 1024
    assert not facts.scope_complete
    assert not seen


@pytest.mark.regression_capture("portable-resource-observation-uncertainty")
def test_optional_provider_load_failure_is_not_fatal(tmp_path: Path) -> None:
    def unavailable():
        raise ImportError("PRIVATE_SENTINEL")

    facts = _observe_portable_resources(tmp_path, "future-platform", loader=unavailable)

    assert facts.host_available_bytes is None
    assert facts.affinity_count is None
    assert not facts.scope_complete
    assert "PRIVATE_SENTINEL" not in repr(facts)


@pytest.mark.regression_capture("portable-resource-observation-uncertainty")
def test_memory_probe_failure_does_not_erase_affinity() -> None:
    def denied():
        raise PermissionError("PRIVATE_SENTINEL")

    provider = _provider()
    provider.virtual_memory = denied
    facts = _read_portable_facts(provider, "linux", None)

    assert facts.host_available_bytes is None
    assert facts.affinity_count == 2
    assert not facts.scope_complete
