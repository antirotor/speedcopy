"""Speedcopy."""
from .copyfile import copyfile, patch_copyfile, unpatch_copyfile
from .version import __version__

__all__ = [
    "__version__",
    "copyfile",
    "patch_copyfile",
    "unpatch_copyfile",
]
