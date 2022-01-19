# -*- coding: utf-8 -*-
"""Speedcopy copyfile replacement.

Speedcopy speeds up copying files over network by utilizing system specific
calls taking advantage of server side copy. This speed increase is visible
when copying file on same share and only if share server supports server
side copy (samba 4.1.0).

See:
    https://wiki.samba.org/index.php/Server-Side_Copy

Attributes:
    SPEEDCOPY_DEBUG (bool): set to print debug messages.

"""
import errno
import os
import shutil
import stat
import sys
import ctypes

SPEEDCOPY_DEBUG = False


def debug(msg):
    """Print debug message to console."""
    if SPEEDCOPY_DEBUG:
        print(msg)


if not sys.platform.startswith("win32"):
    try:
        _sendfile = os.sendfile
    except AttributeError:
        try:
            import sendfile
        except ImportError:
            _sendfile = None
        else:
            _sendfile = sendfile.sendfile
    from fcntl import ioctl
    import ctypes.util
    from ctypes import c_int
    from .fstatfs import FilesystemInfo

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

    def IOC_TYPECHECK(t):
        """Return the size of given ioctl type.

        Returns the size of given type, and check its suitability for use in an
        ioctl command number.

        """
        result = ctypes.sizeof(t)
        assert result <= _IOC_SIZEMASK, result
        return result

    def IOC(dir, type, nr, size):
        """Prepare command for ioctl.

        Args:
            dir (int): One of ``IOC_NONE``, ``IOC_WRITE``, ``IOC_READ``
                       or ``IOC_READ|IOC_WRITE``. Direction is from the
                       application's point of view, not kernel's.
            size (int): (14-bits unsigned integer) Size of the buffer passed
                        to ioctl's "arg" argument.
        """
        assert dir <= _IOC_DIRMASK, dir
        assert type <= _IOC_TYPEMASK, type
        assert nr <= _IOC_NRMASK, nr
        assert size <= _IOC_SIZEMASK, size
        return (dir << _IOC_DIRSHIFT) | (type << _IOC_TYPESHIFT) | (nr << _IOC_NRSHIFT) | (size << _IOC_SIZESHIFT)  # noqa: E501

    def IOW(type, nr, size):
        """Ioctl with write parameters.

        Args:
            size (ctype type or instance): Type/structure of the argument
                                           passed to ioctl's "arg" argument.
        """
        return IOC(IOC_WRITE, type, nr, IOC_TYPECHECK(size))

    # errnos sendfile can set if not supported on the system
    _sendfile_err_codes = {code for code, name in errno.errorcode.items()
                           if name in ("EINVAL", "ENOSYS", "ENOTSUP",
                                       "EBADF", "ENOTSOCK", "EOPNOTSUPP")}

    def _copyfile_sendfile(fsrc, fdst):
        """Copy data from fsrc to fdst using sendfile.

        Args:
            fsrc (str): Source file.
            fdst (str): Destination file.

        Returns:
            bool: True on success.

        """
        if not _sendfile:
            return False
        status = False
        max_bcount = 2 ** 31 - 1
        bcount = max_bcount
        offset = 0
        fdstno = fdst.fileno()
        fsrcno = fsrc.fileno()

        try:
            while bcount > 0:
                bcount = _sendfile(fdstno, fsrcno, offset, max_bcount)
                offset += bcount
                status = True
        except OSError as e:
            if e.errno in _sendfile_err_codes:
                # sendfile is not supported or does not support classic
                # files (only sockets)
                debug("!!! sendfile not supported: {}".format(e.errno))
                pass
            else:
                debug("!!! sendfile other error {}".format(e))
                raise
        return status

    def copyfile(src, dst, follow_symlinks=True):
        """Copy data from src to dst.

        Args:
            src (str): Source file.
            dst (str): Destination file.
            follow_symlinks (bool): If ``follow_symlinks`` is not set and
                ``src`` is a symbolic link, a new symlink will be created
                instead of copying the file it points to.

        Returns:
            str: Destination on success

        Raises:
            shutil.SpecialFileError: when source/destination is invalid.
            shutil.SameFileError: if ``src`` and ``dst`` are same.

        """
        if shutil._samefile(src, dst):
            raise shutil.SameFileError(
                "{!r} and {!r} are the same file".format(src, dst))

        for fn in [src, dst]:
            try:
                st = os.stat(fn)
            except OSError as e:
                # File most likely does not exist
                debug(">>> {} doesn't exists [ {} ]".format(fn, e))
            else:
                # XXX What about other special files? (sockets, devices...)
                if stat.S_ISFIFO(st.st_mode):
                    raise shutil.SpecialFileError("`%s` is a named pipe" % fn)

        if not follow_symlinks and os.path.islink(src):
            debug(">>> creating symlink ...")
            os.symlink(os.readlink(src), dst)
        else:
            fs_src_type = FilesystemInfo().filesystem(src.encode('utf-8'))
            dst_dir_path = os.path.normpath(os.path.dirname(dst.encode('utf-8')))  # noqa: E501
            fs_dst_type = FilesystemInfo().filesystem(dst_dir_path)
            supported_fs = ['CIFS', 'SMB2']
            debug(">>> Source FS: {}".format(fs_src_type))
            debug(">>> Destination FS: {}".format(fs_dst_type))
            if fs_src_type in supported_fs and fs_dst_type in supported_fs:
                fsrc = os.open(src, os.O_RDONLY)
                fdst = os.open(dst, os.O_WRONLY | os.O_CREAT)

                CIFS_IOCTL_MAGIC = 0xCF
                CIFS_IOC_COPYCHUNK_FILE = IOW(CIFS_IOCTL_MAGIC, 3, c_int)

                # try copy file with COW support on Linux. If fail, fallback
                # to sendfile and if this is not available too, fallback
                # copyfileobj.
                ret = ioctl(fdst, CIFS_IOC_COPYCHUNK_FILE, fsrc)
                os.close(fsrc)
                os.close(fdst)
                if ret != 0:
                    debug("!!! failed {}".format(ret))
                    os.close(fsrc)
                    os.close(fdst)
                    # Try to use sendfile if available for performance
                    with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                        if not _copyfile_sendfile(fsrc, fdst):
                            debug("!!! failed sendfile")
                            # sendfile is not available or failed, fallback
                            # to copyfileobj
                            shutil.copyfileobj(fsrc, fdst)
            else:
                with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                    if not _copyfile_sendfile(fsrc, fdst):
                        # sendfile is not available or failed, fallback
                        # to copyfileobj
                        shutil.copyfileobj(fsrc, fdst)

        return dst

else:
    def copyfile(src, dst, follow_symlinks=True):
        """Copy data from src to dst.

        It uses windows native ``CopyFile2`` method to do so, making advantage
        of server-side copy where available. If this method is not available
        it will fallback to ``CopyFileW`` (on Windows 7 and older).

        Args:
            src (str): Source file.
            dst (str): Destination file.
            follow_symlinks (bool): If ``follow_symlinks`` is not set and
                ``src`` is a symbolic link, a new symlink will be created
                instead of copying the file it points to.

        Returns:
            str: Destination on success

        Raises:
            shutil.SpecialFileError: when source/destination is invalid.
            shutil.SameFileError: if ``src`` and ``dst`` are same.
            OSError: if file no exist
            IOError: if copying failed on windows API level.

        """
        if shutil._samefile(src, dst):
            # Get shutil.SameFileError if available (Python 3.4+)
            # else fall back to original behavior using shutil.Error
            SameFileError = getattr(shutil, "SameFileError", shutil.Error)
            raise SameFileError(
                "{!r} and {!r} are the same file".format(src, dst))

        for fn in [src, dst]:
            try:
                st = os.stat(fn)
            except OSError:
                # File most likely does not exist
                pass
            else:
                # XXX What about other special files? (sockets, devices...)
                if stat.S_ISFIFO(st.st_mode):
                    raise shutil.SpecialFileError("`%s` is a named pipe" % fn)

        if not follow_symlinks and os.path.islink(src):
            os.symlink(os.readlink(src), dst)
        else:
            kernel32 = ctypes.WinDLL('kernel32',
                                     use_last_error=True, use_errno=True)
            try:
                copyfile = kernel32.CopyFile2
            except AttributeError:
                # on windows 7 and older
                copyfile = kernel32.CopyFileW

            copyfile.argtypes = (ctypes.c_wchar_p,
                                 ctypes.c_wchar_p,
                                 ctypes.c_void_p)
            copyfile.restype = ctypes.HRESULT

            source_file = os.path.abspath(os.path.normpath(src))
            dest_file = os.path.abspath(os.path.normpath(dst))
            if source_file.startswith('\\\\'):
                source_file = 'UNC\\' + source_file[2:]
            if dest_file.startswith('\\\\'):
                dest_file = 'UNC\\' + dest_file[2:]

            ret = copyfile('\\\\?\\' + source_file,
                           '\\\\?\\' + dest_file, None)

            if ret == 0:
                error = ctypes.get_last_error()
                if error == 0:
                    return dst
                # 997 is ERROR_IO_PENDING. Why it is poping here with
                # CopyFileW is beyond me, but  assume we can easily
                # ignore it as it is copying nevertheless
                if error == 997:
                    return dst
                raise IOError(
                    "File {!r} copy failed, error: {}".format(
                        src, ctypes.FormatError(error)))
        return dst


def patch_copyfile():
    """Monkey patch shutil.copyfile()."""
    if shutil.copyfile != copyfile:
        shutil._orig_copyfile = shutil.copyfile
        shutil.copyfile = copyfile


def unpatch_copyfile():
    """Restore original function."""
    shutil.copyfile = shutil._orig_copyfile
