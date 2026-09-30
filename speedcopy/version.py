"""Version definition."""
VERSION_MAJOR = 2
VERSION_MINOR = 2
VERSION_PATCH = 0

version_info = (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)
version = "%i.%i.%i" % version_info  # ruff: ignore[printf-string-formatting]
__version__ = version

__all__ = ["__version__", "version", "version_info"]
