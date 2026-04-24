"""Speedcopy."""
from .copyfile import (
    SPEEDCOPY_DEBUG,
    copyfile,
    patch_copyfile,
    unpatch_copyfile,
)
from .version import __version__

__all__ = [
    "SPEEDCOPY_DEBUG",
    "__version__",
    "copyfile",
    "patch_copyfile",
    "unpatch_copyfile"
]
