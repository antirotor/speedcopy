"""Windows implementation of copyfile."""
from __future__ import annotations

import ctypes
import os
import shutil
import stat
from typing import Union

# Initialize once on import for performance
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True, use_errno=True)
try:
    COPYFILE = kernel32.CopyFile2
    is_copyfile2 = True
except AttributeError:
    # on Windows 7 and older
    COPYFILE = kernel32.CopyFileW
    is_copyfile2 = False

COPYFILE.restype = ctypes.HRESULT

ERROR_IO_PENDING: int = 997

if is_copyfile2:
    # Skip alternate streams in CopyFile2
    from ctypes import wintypes

    class COPYFILE2_EXTENDED_PARAMETERS(ctypes.Structure):  # noqa: N801
        """Structure to hold extended parameters for CopyFile2.

        Example::
            typedef struct COPYFILE2_EXTENDED_PARAMETERS {
              DWORD                       dwSize;
              DWORD                       dwCopyFlags;
              BOOL                        *pfCancel;
              PCOPYFILE2_PROGRESS_ROUTINE pProgressRoutine;
              PVOID                       pvCallbackContext;
            } COPYFILE2_EXTENDED_PARAMETERS;
        """

        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("dwCopyFlags", wintypes.DWORD),
            # The rest isn't actually void, but by making these
            # voids the call speed is much faster - especially with
            # pProgressRoutine as void instead of WINFUNCTYPE
            ("pfCancel", ctypes.c_void_p),
            ("pProgressRoutine", ctypes.c_void_p),
            ("pvCallbackContext", ctypes.c_void_p),
        ]

    PARAMS = COPYFILE2_EXTENDED_PARAMETERS()
    PARAMS.dwSize = ctypes.sizeof(COPYFILE2_EXTENDED_PARAMETERS)
    PARAMS.dwCopyFlags = 0x00008000  # COPY_FILE_SKIP_ALTERNATE_STREAMS
    COPYFILE.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.POINTER(COPYFILE2_EXTENDED_PARAMETERS),
    )

else:
    COPYFILE.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p)
    PARAMS = None


def copyfile(  # noqa: C901
        src: Union[str, os.PathLike],
        dst: Union[str, os.PathLike],
        *,
        follow_symlinks: bool = True) -> Union[str, os.PathLike]:
    """Copy data from src to dst.

    It uses Windows native ``CopyFile2`` method to do so, making advantage
    of server-side copy where available. If this method is not available
    it will fall back to ``CopyFileW`` (on Windows 7 and older).

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
        SameFileError: if ``src`` and ``dst`` are same.
        OSError: if file no exist
        IOError: if copying failed on Windows API level.

    """  # noqa: DOC502
    if shutil._samefile(src, dst):  # noqa: SLF001
        # Get shutil.SameFileError if available (Python 3.4+)
        # else fall back to original behavior using shutil.Error
        SameFileError = getattr(  # noqa: N806
            shutil, "SameFileError", shutil.Error)
        msg = f"{src!r} and {dst!r} are the same file"
        raise SameFileError(msg)

    for fn in [src, dst]:
        try:
            st = os.stat(fn)
        except OSError:  # noqa: PERF203
            # File most likely does not exist
            pass
        else:
            # What about other special files? (sockets, devices...)
            if stat.S_ISFIFO(st.st_mode):
                msg = f"`{fn}` is a named pipe"
                raise shutil.SpecialFileError(msg)

    if not follow_symlinks and os.path.islink(src):
        os.symlink(os.readlink(src), dst)
    else:
        source_file = os.path.abspath(os.path.normpath(src))
        dest_file = os.path.abspath(os.path.normpath(dst))
        if source_file.startswith("\\\\"):
            source_file = "UNC\\" + source_file[2:]
        if dest_file.startswith("\\\\"):
            dest_file = "UNC\\" + dest_file[2:]

        ret = COPYFILE("\\\\?\\" + source_file, "\\\\?\\" + dest_file, PARAMS)

        if ret == 0:
            error = ctypes.get_last_error()
            if error == 0:
                return dst
            # 997 is ERROR_IO_PENDING. Why it is poping here with
            # CopyFileW is beyond me, but  assume we can easily
            # ignore it as it is copying nevertheless
            if error == ERROR_IO_PENDING:
                return dst
            msg = (
                f"File {src!r} copy failed, error: {ctypes.FormatError(error)}"
            )
            raise OSError(msg)
    return dst
