"""POSIX-specific implementation of file copy."""
from __future__ import annotations

import ctypes.util
import errno
import logging
import os
import shutil
import stat
import sys
from ctypes import c_int
from enum import IntFlag
from fcntl import ioctl  # type: ignore[attr-defined]
from typing import Any, BinaryIO, Type, Union, cast

from .fstatfs import FilesystemInfo

log = logging.getLogger(__name__)

_sendfile = getattr(os, "sendfile", None)

CIFS_MAGIC_NUMBER = 0xFF534D42
SMB2_MAGIC_NUMBER = 0xFE534D42

_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_DIRBITS = 2

_IOC_NRMASK = (1 << _IOC_NRBITS) - 1
_IOC_TYPEMASK = (1 << _IOC_TYPEBITS) - 1
_IOC_SIZEMASK = (1 << _IOC_SIZEBITS) - 1
_IOC_DIRMASK = (1 << _IOC_DIRBITS) - 1

_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS

IOC_NONE = 0
IOC_WRITE = 1
IOC_READ = 2


class IoctlDirection(IntFlag):
    """Direction of ioctl command."""

    NONE = IOC_NONE
    WRITE = IOC_WRITE
    READ = IOC_READ


def ioctl_type_check(_type: Any) -> int:  # ruff: ignore[any-type]
    """Return the size of given ioctl type.

    Returns the size of given type, and check its suitability for use in an
    ioctl command number.

    Args:
        _type (Any): Type to check.

    Returns:
        size (int): Size of given ioctl type.

    Raises:
        TypeError: If the size of the type is larger than the maximum allowed
                   for ioctl command numbers.

    """
    result = ctypes.sizeof(_type)
    if result > _IOC_SIZEMASK:
        msg = f"argument type too large {result} (max {_IOC_SIZEMASK})"
        raise TypeError(msg)
    return result


def ioctl_command(
        direction: IoctlDirection,
        type_: int,
        nr: int,
        size: int) -> int:
    """Prepare command for ioctl.

    Args:
        direction (IoctlDirection): One of ``IOC_NONE``, ``IOC_WRITE``,
            ``IOC_READ`` or ``IOC_READ|IOC_WRITE``. Direction is from the
            application's point of view, not kernel's.
        type_ (int): (8-bits unsigned integer) Type of the ioctl command,
            usually an ASCII character.
        nr (int): (8-bits unsigned integer) Number in series
            (or command number) of the ioctl command.
        size (int): (14-bits unsigned integer) Size of the buffer passed
            to ioctl's "arg" argument.

    Returns:
        int: Command for ioctl.

    Raises:
        ValueError: if passed arguments are wrong.

    """
    if direction < 0 or direction > _IOC_DIRMASK:
        msg = f"invalid direction {direction}"
        raise ValueError(msg)

    if type_ < 0 or type_ > _IOC_TYPEMASK:
        msg = f"invalid type {type_}"
        raise ValueError(msg)

    if nr < 0 or nr > _IOC_NRMASK:
        msg = f"invalid nr {nr}"
        raise ValueError(msg)

    if size < 0 or size > _IOC_SIZEMASK:
        msg = f"invalid size {size}"
        raise ValueError(msg)

    return (
        (direction << _IOC_DIRSHIFT)
        | (type_ << _IOC_TYPESHIFT)
        | (nr << _IOC_NRSHIFT)
        | (size << _IOC_SIZESHIFT)
    )


def ioctl_write(type_: int, nr: int, type_size: Type[c_int]) -> int:
    """Ioctl with write parameters.

    Args:
        type_ (int): Type to send.
        nr (int): Number in sequence of the ioctl command.
        type_size (ctype type or instance): Type/structure of the argument
            passed to ioctl's "arg" argument.

    Returns:
        int: Command result.

    """
    return ioctl_command(
        IoctlDirection.WRITE, type_, nr, ioctl_type_check(type_size))


# errnos sendfile can set if not supported on the system
_sendfile_err_codes = {
    code
    for code, name in errno.errorcode.items()
    if name
    in {"EINVAL", "ENOSYS", "ENOTSUP", "EBADF", "ENOTSOCK", "EOPNOTSUPP"}
}


def _copyfile_sendfile(
        file_src: BinaryIO,
        file_dst: BinaryIO) -> bool:
    """Copy data from fsrc to fdst using sendfile.

    Args:
        file_src (str): Source file.
        file_dst (str): Destination file.

    Returns:
        bool: True on success.

    Raises:
        OSError: When `sendfile` produces error or is not supported.

    """
    if not _sendfile:
        return False
    status = False
    if sys.platform.startswith("darwin"):
        max_bcount = 0
    else:
        max_bcount = 2**31 - 1
    bcount = max_bcount
    offset = 0
    fdstno = file_dst.fileno()
    fsrcno = file_src.fileno()

    try:
        while bcount > 0:
            bcount = _sendfile(fdstno, fsrcno, offset, max_bcount)
            offset += bcount
            status = True
    except OSError as e:
        if e.errno in _sendfile_err_codes:
            # sendfile is not supported or does not support classic
            # files (only sockets)
            log.debug("sendfile not supported %s", e.errno)
        else:
            log.debug("sendfile other error %s", e)
            raise
    return status


def _copyfile_fallback(
        src: Union[str, bytes],
        dst: Union[str, bytes]) -> None:
    """Copy a file using sendfile first, then copyfileobj."""
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        if not _copyfile_sendfile(fsrc, fdst):
            shutil.copyfileobj(fsrc, fdst)


def _coerce_path(path: Union[str, bytes, os.PathLike]) -> Union[str, bytes]:
    """Return a filesystem path as str or bytes.

    Returns:
        str or bytes: Normalized filesystem path.

    """
    return cast("Union[str, bytes]", os.fspath(path))


def copyfile(  # ruff: ignore[complex-structure]
        src: Union[str, bytes, os.PathLike],
        dst: Union[str, bytes, os.PathLike],
        *,
        follow_symlinks: bool = True) -> Union[str, bytes]:
    """Copy data from src to dst.

    Args:
        src (str or os.PathLike): Source file.
        dst (str or os.PathLike): Destination file.
        follow_symlinks (bool): If ``follow_symlinks`` is not set and
            ``src`` is a symbolic link, a new symlink will be created
            instead of copying the file it points to.

    Returns:
        str: Destination on success

    Raises:
        SameFileError: If ``src`` and ``dst`` are the same file.
        SpecialFileError: If ``src`` or ``dst`` is a named pipe.

    """
    src_path = _coerce_path(src)
    dst_path = _coerce_path(dst)

    if shutil._samefile(  # ruff: ignore[private-member-access]  # type: ignore[attr-defined]
            src_path, dst_path):
        msg = f"{src_path!r} and {dst_path!r} are the same file"
        raise shutil.SameFileError(msg)

    for fn in [src_path, dst_path]:
        try:
            st = os.stat(fn)
        except OSError:  # ruff: ignore[try-except-in-loop]
            # File most likely does not exist
            log.debug("%s does not exist yet.", fn)
        else:
            if stat.S_ISFIFO(st.st_mode):
                msg = f"`{fn!r}` is a named pipe"
                raise shutil.SpecialFileError(msg)

    if not follow_symlinks and os.path.islink(src_path):
        log.debug("creating symlink %s -> %s", src_path, dst_path)
        os.symlink(os.readlink(src_path), dst_path)
    else:
        should_try_ioctl = sys.platform.startswith("linux")
        if should_try_ioctl:
            dst_dir_path = os.path.dirname(dst_path)
            if not dst_dir_path:
                dst_dir_path = b"." if isinstance(dst_path, bytes) else "."
            dst_dir_path = os.path.normpath(dst_dir_path)

            fs_info = FilesystemInfo()
            fs_src_type = fs_info.filesystem(src_path)
            fs_dst_type = fs_info.filesystem(dst_dir_path)
            supported_fs = ["CIFS", "SMB2"]
            log.debug("Source FS: %s", fs_src_type)
            log.debug("Destination FS: %s", fs_dst_type)
            if fs_src_type in supported_fs and fs_dst_type in supported_fs:
                fsrc = os.open(src_path, os.O_RDONLY)
                fdst = os.open(dst_path, os.O_WRONLY | os.O_CREAT)
                try:
                    CIFS_IOCTL_MAGIC = 0xCF  # ruff: ignore[non-lowercase-variable-in-function]
                    CIFS_IOC_COPYCHUNK_FILE = ioctl_write(  # ruff: ignore[non-lowercase-variable-in-function]
                        CIFS_IOCTL_MAGIC, 3, c_int)

                    # try copy file with COW support on Linux. If fails,
                    # fallback to sendfile and if this is not available too,
                    # fallback to copyfileobj.
                    ret = ioctl(fdst, CIFS_IOC_COPYCHUNK_FILE, fsrc)
                finally:
                    os.close(fsrc)
                    os.close(fdst)

                if ret == 0:
                    return dst_path

                log.error("Failed %s", ret)

        _copyfile_fallback(src_path, dst_path)

    return dst_path
