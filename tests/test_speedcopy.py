"""Tests for speedcopy."""
from __future__ import annotations

import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import speedcopy

_FILE_SIZE = 5 * 1024 * 1024


@pytest.mark.skip(reason="pyxattr module is not by default installed")
def test_copy_extended_attributes(
        tmp_path_factory: pytest.TempPathFactory) -> None:
    """Test copy with extended attributes.

    This tries to copy file with extended attributes. It requires pyxattr
    module to be installed.

    Tests for issue #24.

    Args:
        tmp_path_factory: pytest fixture for temporary directory.

    """
    import xattr

    tmp_path = tmp_path_factory.mktemp("test_copy_extended_attributes")

    src = tmp_path / "source"
    dst = tmp_path / "destination"

    with open(src, "wb") as f:
        f.write(os.urandom(_FILE_SIZE))
    f.close()
    xattr.setxattr(src.as_posix(), "user.comment", "xattr test")

    shutil.copyfile(src, dst)

    assert os.path.isfile(str(dst))
    assert xattr.getxattr(dst.as_posix(), "user.comment") == "xattr test"


def test_copy_alternate_data_streams(
        tmp_path_factory: pytest.TempPathFactory) -> None:
    """Test copy with alternate data streams.

    Speedcopy should ignore alternate data streams.

    Args:
        tmp_path_factory: pytest fixture for temporary directory.


    """
    tmp_path = tmp_path_factory.mktemp("test_copy_alternate_data_streams")

    src = tmp_path / "source"
    dst = tmp_path / "destination"

    with open(src, "wb") as f:
        f.write(os.urandom(_FILE_SIZE))
    f.close()
    with open(src.as_posix() + ":ads", "wb") as f:
        f.write(os.urandom(_FILE_SIZE))
    f.close()

    shutil.copyfile(src, dst)

    # alternate data stream should be ignored, but the file it
    # is attached to should be copied
    assert dst.exists()
    assert not os.path.isfile(dst.as_posix() + ":ads")


def test_copy_abs(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Test copy from absolute paths.

    Args:
        tmp_path_factory: pytest fixture for temporary directory.

    """
    tmp_path = tmp_path_factory.mktemp("test_copy_abs")
    src = tmp_path / "source"
    dst = tmp_path / "destination"
    with open(src, "wb") as f:
        f.write(os.urandom(_FILE_SIZE))
    f.close()

    shutil.copyfile(src, dst)

    assert os.path.isfile(dst)


def test_copy_rel(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Test copy from relative paths.

    Args:
        tmp_path_factory: pytest fixture for temporary directory.

    """
    cwd = os.getcwd()
    tmp_path = tmp_path_factory.mktemp("test_copy_rel")
    os.chdir(str(tmp_path))

    try:
        src = "source"
        dst = "destination"
        with open(str(src), "wb") as f:
            f.write(os.urandom(_FILE_SIZE))
        f.close()

        shutil.copyfile(str(src), str(dst))

        assert os.path.isfile(str(dst))
    finally:
        os.chdir(cwd)


def test_copy_threadpool_multi_thread(
        tmp_path_factory: pytest.TempPathFactory) -> None:
    """Test concurrent copy operations using a thread pool."""
    tmp_path = tmp_path_factory.mktemp("test_copy_threadpool_multi_thread")
    pairs = []
    for idx in range(8):
        src = tmp_path / f"source_{idx}"
        dst = tmp_path / f"destination_{idx}"
        payload = bytes([idx]) * (64 * 1024)
        src.write_bytes(payload)
        pairs.append((src, dst))

    thread_ids: set[int] = set()
    lock = threading.Lock()

    def copy_one(src_dst: tuple[os.PathLike[str], os.PathLike[str]]) -> None:
        src, dst = src_dst
        with lock:
            thread_ids.add(threading.get_ident())
        shutil.copyfile(src, dst)

    was_patched = shutil.copyfile == speedcopy.copyfile
    if not was_patched:
        speedcopy.patch_copyfile()

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(copy_one, pairs))
    finally:
        if not was_patched:
            speedcopy.unpatch_copyfile()

    assert len(thread_ids) >= 2
    for src, dst in pairs:
        assert dst.exists()
        assert src.read_bytes() == dst.read_bytes()


def test_errors(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Exception IOError should be raised if file doesn't exist.

    Args:
        tmp_path_factory: pytest fixture for temporary directory.

    """
    tmp_path = tmp_path_factory.mktemp("test_errors")
    src = tmp_path / "source"
    dst = tmp_path / "destination"

    with pytest.raises((IOError, OSError)):
        shutil.copyfile(src, dst)


def test_patch() -> None:
    """Test if copyfile is patched."""
    speedcopy.patch_copyfile()
    assert shutil.copyfile == speedcopy.copyfile
    assert hasattr(shutil, "_orig_copyfile")


def test_unpatch() -> None:
    """Test if copyfile is restored."""
    speedcopy.patch_copyfile()
    speedcopy.unpatch_copyfile()
    assert shutil.copyfile == shutil._orig_copyfile  # noqa: SLF001
