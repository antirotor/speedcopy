"""Sync package version between pyproject.toml and speedcopy/version.py.

Usage:
    version_sync.py check [--tag TAG]  # fail if versions (and tag) differ
    version_sync.py sync               # copy pyproject version to version.py
    version_sync.py info               # print version, tag and prerelease flag

``info`` also appends the values to ``$GITHUB_OUTPUT`` when it is set.
"""

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
VERSION_FILE = ROOT / "speedcopy" / "version.py"

PYPROJECT_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
VERSION_FILE_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)
PRERELEASE_RE = re.compile(r"(a|b|rc|\.dev)\d+")


def _read(path: Path, pattern: re.Pattern) -> str:
    match = pattern.search(path.read_text(encoding="utf-8"))
    if not match:
        sys.exit(f"::error file={path}::Version not found")
    return match.group(1)


def pyproject_version() -> str:
    """Return version declared in pyproject.toml."""
    return _read(PYPROJECT, PYPROJECT_RE)


def package_version() -> str:
    """Return version declared in speedcopy/version.py."""
    return _read(VERSION_FILE, VERSION_FILE_RE)


def check(tag: "str | None") -> int:
    """Validate that all version sources agree."""
    expected = pyproject_version()
    errors = []
    actual = package_version()
    if actual != expected:
        errors.append(
            f"speedcopy/version.py has {actual!r}, "
            f"pyproject.toml has {expected!r}"
        )
    if tag is not None and tag != f"v{expected}":
        errors.append(f"tag {tag!r} does not match 'v{expected}'")
    for error in errors:
        print(f"::error::{error}")
    if not errors:
        print(f"Version {expected} is consistent.")
    return 1 if errors else 0


def sync() -> int:
    """Write pyproject.toml version into speedcopy/version.py."""
    new = pyproject_version()
    text = VERSION_FILE.read_text(encoding="utf-8")
    text = VERSION_FILE_RE.sub(f'__version__ = "{new}"', text, count=1)
    VERSION_FILE.write_text(text, encoding="utf-8")
    print(f"speedcopy/version.py set to {new}")
    return 0


def info() -> int:
    """Print version metadata, also as GitHub Actions step outputs."""
    ver = pyproject_version()
    values = {
        "version": ver,
        "tag": f"v{ver}",
        "prerelease": str(bool(PRERELEASE_RE.search(ver))).lower(),
    }
    lines = [f"{key}={value}" for key, value in values.items()]
    print("\n".join(lines))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")
    return 0


def main() -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--tag")
    sub.add_parser("sync")
    sub.add_parser("info")
    args = parser.parse_args()
    if args.command == "check":
        return check(args.tag)
    if args.command == "sync":
        return sync()
    return info()


if __name__ == "__main__":
    sys.exit(main())
