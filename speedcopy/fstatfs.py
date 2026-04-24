"""Python fstatfs implementation.

Taken from:
https://github.com/mithro/rcfiles

"""
from __future__ import annotations

import ctypes
import ctypes.util
import os
from typing import TYPE_CHECKING, ClassVar, Union, cast

if TYPE_CHECKING:
    from io import IOBase

libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


class FsTypes:
    """Constants for filesystem magic.

    See:
        https://www.gnu.org/software/coreutils/filesystems.html
    """

    filesystems: ClassVar[dict[str, int]] = {
        "AAFS_SUPER_MAGIC": 0x5A3C69F0,
        "ADFS_SUPER_MAGIC": 0xadf5,
        "AFS_SUPER_MAGIC": 0x5346414F,
        "AFFS_SUPER_MAGIC": 0xADFF,
        "BEFS_SUPER_MAGIC": 0x42465331,
        "BFS_MAGIC": 0x1BADFACE,
        "BTRFS_SUPER_MAGIC": 0x9123683E,
        "CIFS_SUPER_MAGIC": 0xFF534D42,
        "CODA_SUPER_MAGIC": 0x73757245,
        "COH_SUPER_MAGIC": 0x012FF7B7,
        "CRAMFS_MAGIC": 0x28cd3d45,
        "DEVFS_SUPER_MAGIC": 0x1373,
        "EFS_SUPER_MAGIC": 0x00414A53,
        "EXT_SUPER_MAGIC": 0x137D,
        "EXT2_OLD_SUPER_MAGIC": 0xEF51,
        "EXT2_SUPER_MAGIC": 0xEF53,
        "EXT3_SUPER_MAGIC": 0xEF53,
        "EXFS_SUPER_MAGIC": 0x45584653,
        "HFS_SUPER_MAGIC": 0x4244,
        "HPFS_SUPER_MAGIC": 0xF995E849,
        "HUGETLBFS_MAGIC": 0x958458f6,
        "ISOFS_SUPER_MAGIC": 0x9660,
        "JFFS2_SUPER_MAGIC": 0x72b6,
        "JFS_SUPER_MAGIC": 0x3153464a,
        "MINIX_SUPER_MAGIC": 0x137F,  # orig. minix
        "MINIX_SUPER_MAGIC2": 0x138F,  # 30 char minix
        "MINIX2_SUPER_MAGIC": 0x2468,  # minix V2
        "MINIX2_SUPER_MAGIC2": 0x2478,  # minix V2, 30 char names
        "MSDOS_SUPER_MAGIC": 0x4d44,
        "NCP_SUPER_MAGIC": 0x564c,
        "NFS_SUPER_MAGIC": 0x6969,
        "NTFS_SB_MAGIC": 0x5346544e,
        "OPENPROM_SUPER_MAGIC": 0x9fa1,
        "PROC_SUPER_MAGIC": 0x9fa0,
        "QNX4_SUPER_MAGIC": 0x002f,
        "REISERFS_SUPER_MAGIC": 0x52654973,
        "ROMFS_MAGIC": 0x7275,
        "SMB_SUPER_MAGIC": 0x517B,
        "SMB2_SUPER_MAGIC": 0xfe534d42,
        "SYSV2_SUPER_MAGIC": 0x012FF7B6,
        "SYSV4_SUPER_MAGIC": 0x012FF7B5,
        "TMPFS_MAGIC": 0x01021994,
        "UDF_SUPER_MAGIC": 0x15013346,
        "UFS_MAGIC": 0x00011954,
        "USBDEVICE_SUPER_MAGIC": 0x9fa2,
        "VXFS_SUPER_MAGIC": 0xa501FCF5,
        "XENIX_SUPER_MAGIC": 0x012FF7B4,
        "XFS_SUPER_MAGIC": 0x58465342,
        "_XIAFS_SUPER_MAGIC": 0x012FD16D,
    }

    types: ClassVar[dict[int, str]] = {}

    def __init__(self):
        """Remove ``MAGIC`` and ``SUPER`` postfixes."""
        for name, value in self.filesystems.items():
            if name.endswith("MAGIC"):
                hname = name[:-6]
                hname = hname.replace("_SUPER", "")
                self.types[value] = hname


class statfs_t(ctypes.Structure):  # noqa: N801
    """Describes the details about a filesystem.

    Attributes:
        f_type:    type of file system (see below)
        f_bsize:   optimal transfer block size
        f_blocks:  total data blocks in file system
        f_bfree:   free blocks in fs
        f_bavail:  free blocks avail to non-superuser
        f_files:   total file nodes in file system
        f_ffree:   free file nodes in fs
        f_fsid:    file system id
        f_namelen: maximum length of filenames
        padding:   padding

    """

    _fields_ = [
        ("f_type", ctypes.c_long),  # type of file system (see below)
        ("f_bsize", ctypes.c_long),  # optimal transfer block size
        ("f_blocks", ctypes.c_long),  # total data blocks in file system
        ("f_bfree", ctypes.c_long),  # free blocks in fs
        ("f_bavail", ctypes.c_long),  # free blocks avail to non-superuser
        ("f_files", ctypes.c_long),  # total file nodes in file system
        ("f_ffree", ctypes.c_long),  # free file nodes in fs
        ("f_fsid", ctypes.c_int * 2),  # file system id
        ("f_namelen", ctypes.c_long),  # maximum length of filenames
        # statfs_t has a bunch of extra padding,
        # we hopefully guess large enough.
        ("padding", ctypes.c_char * 1024),
    ]


class FilesystemInfo:
    """Get filesystem info."""

    def __init__(self):
        """Prepare system calls."""
        self._statfs = libc.statfs
        self._statfs.argtypes = [ctypes.c_char_p, ctypes.POINTER(statfs_t)]
        self._statfs.rettype = ctypes.c_int

        self._fstatfs = libc.fstatfs
        self._fstatfs.argtypes = [ctypes.c_int, ctypes.POINTER(statfs_t)]
        self._fstatfs.rettype = ctypes.c_int

    def statfs(self, path: Union[str, bytes, os.PathLike]) -> statfs_t:
        """Get information about mounted file system by path.

        Args:
            path (str): is the pathname of any file within
                        the mounted file system.

        Returns:
            Returns a statfs_t object.

        Raises:
            OSError: if the path does not exist.

        """
        fs_path = os.fspath(path)
        path_bytes = os.fsencode(fs_path)
        path_text = os.fsdecode(fs_path)

        buf = statfs_t()
        err = self._statfs(path_bytes, ctypes.byref(buf))
        if err == -1:
            errno = ctypes.get_errno()
            msg = (
                f"{os.strerror(errno)} path: {path_text}"
            )
            raise OSError(errno, msg)
        return buf

    def fstatfs(self, fd: IOBase) -> statfs_t:
        """Get information about mounted file system by file descriptor.

        Args:
            fd (IOBase): A file descriptor.

        Returns:
            Returns a statfs_t object.

        Raises:
            OSError: if the file descriptor does not exist.
            ValueError: if the file descriptor does not exist.

        """
        buf = statfs_t()
        try:
            fileno = fd.fileno()
        except OSError as e:
            msg = "File descriptor does not exist."
            raise ValueError(msg) from e
        if fileno < 0:
            msg = "File descriptor is invalid."
            raise ValueError(msg)
        err = self._fstatfs(fileno, ctypes.byref(buf))
        if err == -1:
            errno = ctypes.get_errno()
            raise OSError(errno, os.strerror(errno))
        return buf

    def filesystem(
        self,
        path_or_fd: Union[str, bytes, os.PathLike, IOBase],
    ) -> str:
        """Get the filesystem type a file/path is on.

        Args:
            path_or_fd (str or IOBase): A string path or an object which has
                a IOBase.fileno() function.

        Returns:
            A string name of the file system.

        Raises:
            ValueError: if the path or file descriptor does not exist.

        """
        if hasattr(path_or_fd, "fileno"):
            buf = self.fstatfs(cast("IOBase", path_or_fd))
        else:
            buf = self.statfs(path_or_fd)

        if not buf:
            msg = f"Could not get filesystem information for {path_or_fd!r}"
            raise ValueError(msg)
        f_types = FsTypes().types
        try:
            return f_types[buf.f_type]
        except KeyError:
            return "UNKNOWN"
