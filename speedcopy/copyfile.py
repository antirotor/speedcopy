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
import shutil
import sys

SPEEDCOPY_DEBUG = False


if not sys.platform.startswith("win32"):
    from .posix import copyfile
else:
    from .win import copyfile


def patch_copyfile() -> None:
    """Monkey patch shutil.copyfile()."""
    if shutil.copyfile != copyfile:
        shutil._orig_copyfile = shutil.copyfile  # ruff: ignore[private-member-access]
        shutil.copyfile = copyfile


def unpatch_copyfile() -> None:
    """Restore original function."""
    shutil.copyfile = shutil._orig_copyfile  # ruff: ignore[private-member-access]
