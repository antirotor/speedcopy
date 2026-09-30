"""Version definition.

``__version__`` must match ``version`` in ``pyproject.toml``. The release
workflow keeps them in sync via ``.github/scripts/version_sync.py`` and CI
fails if they drift apart.
"""

import re

__version__ = "2.2.1a1"

version = __version__
version_info = tuple(
    int(part)
    for part in re.match(r"(\d+)\.(\d+)\.(\d+)", __version__).groups()  # type: ignore[union-attr]
)

__all__ = ["__version__", "version", "version_info"]
