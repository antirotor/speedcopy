"""Unit tests for FilesystemInfo in speedcopy.fstatfs."""
from __future__ import annotations

import ctypes
import errno
import os
from io import IOBase
from pathlib import Path
from typing import Callable, cast

import pytest

try:
    from speedcopy.fstatfs import FilesystemInfo, FsTypes, statfs_t
except (AttributeError, OSError, TypeError):
    pytest.skip(
        "speedcopy.fstatfs is unavailable on this platform",
        allow_module_level=True,
    )


class DummyFd(IOBase):
    """Simple file-like object exposing fileno()."""

    def __init__(self, fd: int) -> None:
        """Store a fake file descriptor integer."""
        self._fd = fd

    def fileno(self) -> int:
        """Return the fake file descriptor.

        Returns:
            int: Fake file descriptor.

        """
        return self._fd


class StubFilesystemInfo(FilesystemInfo):
    """FilesystemInfo with injectable syscall callables for unit tests."""

    def __init__(
        self,
        statfs_impl: Callable[[bytes, object], int],
        fstatfs_impl: Callable[[int, object], int],
    ) -> None:
        """Inject stub syscall functions used by FilesystemInfo methods."""
        super().__init__()
        self._statfs = statfs_impl
        self._fstatfs = fstatfs_impl


def _set_fs_type(buf_ref: object, fs_type: int) -> None:
    """Populate f_type on a statfs_t byref pointer."""
    ptr = ctypes.cast(  # type: ignore[arg-type]
        buf_ref,
        ctypes.POINTER(statfs_t),
    )
    ptr.contents.f_type = fs_type


def test_statfs_returns_populated_statfs_buffer() -> None:
    """statfs() returns a buffer filled by the native call."""

    def fake_statfs(path: bytes, buf_ref: object) -> int:
        assert path == b"/share/source"
        _set_fs_type(buf_ref, FsTypes.filesystems["CIFS_MAGIC_NUMBER"])
        return 0

    fs_info = StubFilesystemInfo(fake_statfs, lambda _fd, _buf: 0)

    result = fs_info.statfs("/share/source")

    assert isinstance(result, statfs_t)
    assert result.f_type == FsTypes.filesystems["CIFS_MAGIC_NUMBER"]


def test_statfs_raises_oserror_on_native_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """statfs() surfaces errno and path details on failure."""

    def fake_statfs(_path: bytes, _buf_ref: object) -> int:
        return -1

    fs_info = StubFilesystemInfo(fake_statfs, lambda _fd, _buf: 0)
    monkeypatch.setattr(ctypes, "get_errno", lambda: errno.ENOENT)

    with pytest.raises(OSError, match="path: /missing") as exc_info:
        fs_info.statfs("/missing")

    assert exc_info.value.errno == errno.ENOENT
    assert "path: /missing" in str(exc_info.value)


def test_fstatfs_returns_populated_statfs_buffer() -> None:
    """fstatfs() returns a buffer filled by the native call."""

    def fake_fstatfs(fd: int, buf_ref: object) -> int:
        assert fd == 9
        _set_fs_type(buf_ref, FsTypes.filesystems["SMB2_SUPER_MAGIC"])
        return 0

    fs_info = StubFilesystemInfo(lambda _path, _buf: 0, fake_fstatfs)

    result = fs_info.fstatfs(cast("IOBase", DummyFd(9)))

    assert isinstance(result, statfs_t)
    assert result.f_type == FsTypes.filesystems["SMB2_SUPER_MAGIC"]


def test_fstatfs_raises_value_error_for_missing_descriptor() -> None:
    """fstatfs() rejects false-y file descriptors."""
    fs_info = StubFilesystemInfo(lambda _path, _buf: 0, lambda _fd, _buf: 0)

    with pytest.raises(ValueError, match="File descriptor does not exist"):
        fs_info.fstatfs(cast("IOBase", DummyFd(0)))


def test_fstatfs_raises_oserror_on_native_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fstatfs() surfaces errno on failure."""

    def fake_fstatfs(_fd: int, _buf_ref: object) -> int:
        return -1

    fs_info = StubFilesystemInfo(lambda _path, _buf: 0, fake_fstatfs)
    monkeypatch.setattr(ctypes, "get_errno", lambda: errno.EIO)

    with pytest.raises(OSError, match=r".*") as exc_info:
        fs_info.fstatfs(cast("IOBase", DummyFd(11)))

    assert exc_info.value.errno == errno.EIO


def test_filesystem_routes_to_statfs_for_paths() -> None:
    """filesystem() uses statfs() for path-like input."""

    def fake_statfs(path: bytes, buf_ref: object) -> int:
        assert path == b"/mnt/share"
        _set_fs_type(buf_ref, FsTypes.filesystems["CIFS_MAGIC_NUMBER"])
        return 0

    fs_info = StubFilesystemInfo(fake_statfs, lambda _fd, _buf: 0)

    assert fs_info.filesystem("/mnt/share") == "CIFS"


def test_filesystem_routes_to_fstatfs_for_file_objects() -> None:
    """filesystem() uses fstatfs() when fileno() is available."""

    def fake_fstatfs(fd: int, buf_ref: object) -> int:
        assert fd == 13
        _set_fs_type(buf_ref, FsTypes.filesystems["SMB2_SUPER_MAGIC"])
        return 0

    fs_info = StubFilesystemInfo(lambda _path, _buf: 0, fake_fstatfs)

    assert fs_info.filesystem(cast("IOBase", DummyFd(13))) == "SMB2"


def test_filesystem_accepts_pathlike_paths() -> None:
    """filesystem() normalizes PathLike input before calling statfs()."""

    def fake_statfs(path: bytes, buf_ref: object) -> int:
        assert path == os.fsencode("/mnt/pathlike")
        _set_fs_type(buf_ref, FsTypes.filesystems["CIFS_MAGIC_NUMBER"])
        return 0

    fs_info = StubFilesystemInfo(fake_statfs, lambda _fd, _buf: 0)

    assert fs_info.filesystem(Path("/mnt/pathlike")) == "CIFS"


def test_filesystem_returns_unknown_for_unmapped_type() -> None:
    """filesystem() returns UNKNOWN for unsupported magic values."""

    def fake_statfs(_path: str, buf_ref: object) -> int:
        _set_fs_type(buf_ref, 0xDEADBEEF)
        return 0

    fs_info = StubFilesystemInfo(fake_statfs, lambda _fd, _buf: 0)

    assert fs_info.filesystem("/weird") == "UNKNOWN"


def test_filesystem_raises_value_error_when_no_buffer_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """filesystem() raises when statfs/fstatfs does not yield a buffer."""
    fs_info = StubFilesystemInfo(lambda _path, _buf: 0, lambda _fd, _buf: 0)
    monkeypatch.setattr(fs_info, "statfs", lambda _path: None)

    with pytest.raises(
        ValueError,
        match="Could not get filesystem information",
    ):
        fs_info.filesystem("/invalid")
