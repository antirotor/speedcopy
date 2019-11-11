"""
Speed up shutil.copyfile by using sendfile system call and robocopy for
windows. Based on `pyfastcopy`, extending it to windows.
"""
import errno
import os
import shutil
import stat
import sys


if not sys.platform.startswith("win32"):
    try:
        _sendfile = os.sendfile
    except AttributeError:
        import sendfile
        _sendfile = sendfile.sendfile
    from fcntl import ioctl
    import ctypes

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
        """
        Returns the size of given type, and check its suitability for use in an
        ioctl command number.
        """
        result = ctypes.sizeof(t)
        assert result <= _IOC_SIZEMASK, result
        return result

    def IOC(dir, type, nr, size):
        """
        dir
            One of IOC_NONE, IOC_WRITE, IOC_READ, or IOC_READ|IOC_WRITE.
            Direction is from the application's point of view, not kernel's.
        size (14-bits unsigned integer)
            Size of the buffer passed to ioctl's "arg" argument.
        """
        assert dir <= _IOC_DIRMASK, dir
        assert type <= _IOC_TYPEMASK, type
        assert nr <= _IOC_NRMASK, nr
        assert size <= _IOC_SIZEMASK, size
        return (dir << _IOC_DIRSHIFT) | (type << _IOC_TYPESHIFT) | (nr << _IOC_NRSHIFT) | (size << _IOC_SIZESHIFT)  # noqa: E501

    def IOW(type, nr, size):
        """
        An ioctl with write parameters.
        size (ctype type or instance)
            Type/structure of the argument passed to ioctl's "arg" argument.
        """
        return IOC(IOC_WRITE, type, nr, IOC_TYPECHECK(size))

    # errnos sendfile can set if not supported on the system
    _sendfile_err_codes = {code for code, name in errno.errorcode.items()
                           if name in ("EINVAL", "ENOSYS", "ENOTSUP",
                                       "EBADF", "ENOTSOCK", "EOPNOTSUPP")}

    def _copyfile_sendfile(fsrc, fdst):
        """
        Copy data from fsrc to fdst using sendfile, return True if success.
        """
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
                pass
            else:
                raise
        return status

    def copyfile(src, dst, follow_symlinks=True):
        """Copy data from src to dst.
        If follow_symlinks is not set and src is a symbolic link, a new
        symlink will be created instead of copying the file it points to.
        """
        if shutil._samefile(src, dst):
            raise shutil.SameFileError(
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
            CIFS_IOCTL_MAGIC = 0xCF
            CIFS_IOC_COPYCHUNK_FILE = IOW(CIFS_IOCTL_MAGIC, 3, int)
            with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
                # try copy file with COW support on Linux. If fail, fallback
                # to sendfile and if this is not available too, fallback
                # copyfileobj.
                ret = ioctl(fdst, CIFS_IOC_COPYCHUNK_FILE, fsrc)
                if ret != 0:
                    # Try to use sendfile if available for performance
                    if not _copyfile_sendfile(fsrc, fdst):
                        # sendfile is not available or failed, fallback
                        # to copyfileobj
                        shutil.copyfileobj(fsrc, fdst)
        return dst

else:
    def copyfile(src, dst, follow_symlinks=True):
        """Copy data from src to dst.
        It uses windows native CopyFileW method to do so, making advantage of
        server-side copy where available.
        """
        from ctypes import windll, c_wchar_p, c_int

        kernel32 = windll.kernel32
        copy_file_w = kernel32.CopyFileW
        copy_file_w.argtypes = (c_wchar_p, c_wchar_p, c_int)
        copy_file_w.restype = c_int

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
            ret = copy_file_w(src, dst, False)

            if ret != 0:
                raise IOError(
                    "File {!r} copy failed, error: {}".format(src, ret))
        return dst


def patch_copyfile():
    """
    Used to monkey patch shutil.copyfile()
    """
    if shutil.copyfile != copyfile:
        shutil._orig_copyfile = shutil.copyfile
        shutil.copyfile = copyfile


def unpatch_copyfile():
    """
    Restore original function
    """
    shutil.copyfile = shutil._orig_copyfile
