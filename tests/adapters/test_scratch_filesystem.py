"""Filesystem evidence is separate from admission and physical storage limits."""

import sys
from pathlib import Path

import pytest

from recon_core.adapters._scratch_filesystem import (
    _linux_mount_evidence,
    _observe_scratch_filesystem,
)


@pytest.mark.regression_capture("scratch-filesystem-scope-evidence")
def test_linux_mount_identity_not_longest_path_guess() -> None:
    mounts = (
        "41 1 8:1 / / rw - ext4 /dev/sda rw\n"
        "42 41 8:1 /private /tmp/test rw - ext4 /dev/sda rw\n"
        "43 42 0:55 / /tmp/test rw - nfs server:/data rw\n"
    )
    first = _linux_mount_evidence("mnt_id:\t42\n", mounts, (8, 1))
    assert first.local_candidate is True
    assert first.mount_identity == (42,)
    remote = _linux_mount_evidence("mnt_id:\t43\n", mounts, (0, 55))
    assert remote.local_candidate is False
    assert remote.mount_identity == (43,)


@pytest.mark.parametrize(
    ("fdinfo", "device", "kind"),
    [
        ("mnt_id: 99", (8, 1), "ext4"),
        ("mnt_id: 42", (8, 2), "ext4"),
        ("mnt_id: 42\nmnt_id: 42", (8, 1), "ext4"),
        ("mnt_id: 42", (8, 1), "overlay"),
        ("mnt_id: 42", (8, 1), "futurefs"),
    ],
)
def test_unverified_mount_is_not_local_proof(
    fdinfo: str, device: tuple[int, int], kind: str
) -> None:
    evidence = _linux_mount_evidence(fdinfo, f"42 1 8:1 / /scratch rw - {kind} source rw\n", device)
    assert evidence.local_candidate is None


def test_readonly_mount_does_not_qualify() -> None:
    evidence = _linux_mount_evidence(
        "mnt_id: 42", "42 1 8:1 / /scratch ro - ext4 source rw\n", (8, 1)
    )
    assert evidence.writable is False


@pytest.mark.skipif(sys.platform not in ("linux", "darwin", "win32"), reason="Native evidence lane")
def test_actual_scratch_filesystem_evidence(tmp_path: Path) -> None:
    path = tmp_path.resolve()
    evidence = _observe_scratch_filesystem(path)
    assert evidence.mount_identity is not None
    assert evidence.writable is True
    assert evidence.filesystem is not None
    if sys.platform in ("win32", "darwin"):
        assert evidence.local_candidate is True
        assert evidence.ownership_supported is True
    child = path / "child"
    child.mkdir()
    other = _observe_scratch_filesystem(child)
    assert other.mount_identity == evidence.mount_identity
    assert not hasattr(evidence, "source")


def test_missing_scratch_is_unknown(tmp_path: Path) -> None:
    evidence = _observe_scratch_filesystem(tmp_path / "missing")
    assert evidence.local_candidate is None
    assert evidence.mount_identity is None
    assert evidence.writable is None
