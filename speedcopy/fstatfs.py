# -*- coding: utf-8 -*-
"""Python fstatfs implementation.

Taken from:
https://github.com/mithro/rcfiles

"""
import os
import ctypes
import ctypes.util


libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)


class Fs_types:
    """Constants for filesystem magic.

    See:
        https://www.gnu.org/software/coreutils/filesystems.html
    """

    filesystems = {
        "ADFS_SUPER_MAGIC": 0xadf5,
        "AFFS_SUPER_MAGIC": 0xADFF,
        "BEFS_SUPER_MAGIC": 0x42465331,
        "BFS_MAGIC": 0x1BADFACE,
        "CIFS_MAGIC_NUMBER": 0xFF534D42,
        "CODA_SUPER_MAGIC": 0x73757245,
        "COH_SUPER_MAGIC": 0x012FF7B7,
        "CRAMFS_MAGIC": 0x28cd3d45,
        "DEVFS_SUPER_MAGIC": 0x1373,
        "EFS_SUPER_MAGIC": 0x00414A53,
        "EXT_SUPER_MAGIC": 0x137D,
        "EXT2_OLD_SUPER_MAGIC": 0xEF51,
        "EXT2_SUPER_MAGIC": 0xEF53,
        "EXT3_SUPER_MAGIC": 0xEF53,
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
        "_XIAFS_SUPER_MAGIC": 0x012FD16D
    }

    types = {}

    def __init__(self):
        """Remove ``MAGIC`` and ``SUPER`` postfixes."""
        for name, value in self.filesystems.items():
            if name.endswith('MAGIC'):
                hname = name[:-6]
                hname = hname.replace('_SUPER', '')
                self.types[value] = hname


class statfs_t(ctypes.Structure):
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
    """

    _fields_ = [
        ("f_type",    ctypes.c_long),   # type of file system (see below)
        ("f_bsize",   ctypes.c_long),   # optimal transfer block size
        ("f_blocks",  ctypes.c_long),   # total data blocks in file system
        ("f_bfree",   ctypes.c_long),   # free blocks in fs
        ("f_bavail",  ctypes.c_long),   # free blocks avail to non-superuser
        ("f_files",   ctypes.c_long),   # total file nodes in file system
        ("f_ffree",   ctypes.c_long),   # free file nodes in fs
        ("f_fsid",    ctypes.c_int*2),  # file system id
        ("f_namelen", ctypes.c_long),   # maximum length of filenames
        # statfs_t has a bunch of extra padding,
        # we hopefully guess large enough.
        ("padding",   ctypes.c_char*1024),
    ]


class FilesystemInfo():
    """Get filesystem info."""

    def __init__(self):
        """Prepare system calls."""
        self._statfs = libc.statfs
        self._statfs.argtypes = [ctypes.c_char_p, ctypes.POINTER(statfs_t)]
        self._statfs.rettype = ctypes.c_int

        self._fstatfs = libc.fstatfs
        self._fstatfs.argtypes = [ctypes.c_int, ctypes.POINTER(statfs_t)]
        self._fstatfs.rettype = ctypes.c_int

    def statfs(self, path):
        """Get information about mounted file system by path.

        Args:
            path (str): is the pathname of any file within
                        the mounted file system.

        Returns:
            Returns a statfs_t object.

        """
        buf = statfs_t()
        err = self._statfs(path, ctypes.byref(buf))
        if err == -1:
            errno = ctypes.get_errno()
            raise OSError(errno, '%s path: %r' % (os.strerror(errno), path))
        return buf

    def fstatfs(self, fd):
        """Get information about mounted file system by file descriptor.

        Args:
            fd: A file descriptor.
        Returns:
            Returns a statfs_t object.

        """
        buf = statfs_t()
        fileno = fd.fileno()
        assert fileno
        err = self._fstatfs(fileno, ctypes.byref(buf))
        if err == -1:
            errno = ctypes.get_errno()
            raise OSError(errno, os.strerror(errno))
        return buf

    def filesystem(self, path_or_fd):
        """Get the filesystem type a file/path is on.

        Args:
            path_or_fd (str or IOBase): A string path or an object which has
                                        a :meth:`IOBase.fileno()` function.
        Returns:
            A string name of the file system.
        """
        if hasattr(path_or_fd, 'fileno'):
            buf = self.fstatfs(path_or_fd)
        else:
            buf = self.statfs(path_or_fd)

        assert buf
        f_types = Fs_types().types
        try:
            return f_types[buf.f_type]
        except KeyError:
            return "UNKNOWN"
