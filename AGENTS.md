# AGENTS Guide for `speedcopy`

## Mission and Scope
- Keep `speedcopy` a drop-in acceleration path for `shutil.copyfile` on SMB/CIFS shares.
- Preserve `shutil.copyfile`-compatible behavior first; optimize only when platform paths support it.
- Prefer small, targeted edits in `speedcopy/` and behavior-focused tests in `tests/`.

## Project Map (edit here first)
- `speedcopy/copyfile.py`: platform dispatch + monkeypatch API (`patch_copyfile`, `unpatch_copyfile`).
- `speedcopy/win.py`: Windows backend using `CopyFile2`/`CopyFileW` via `ctypes`.
- `speedcopy/posix.py`: POSIX backend with CIFS ioctl + `sendfile` + `copyfileobj` fallback chain.
- `speedcopy/fstatfs.py`: filesystem type detection used by POSIX backend.
- `speedcopy/__init__.py`: public exports; keep API surface stable.
- `tests/test_speedcopy.py`: current behavior checks and patch/unpatch expectations.
- `pyproject.toml`: canonical metadata, Ruff rules, dev tooling.

## Non-Negotiable Behavior Patterns
- Keep `copyfile` signatures compatible with stdlib shape:
  - `copyfile(src, dst, *, follow_symlinks=True) -> dst`
- Keep monkeypatch semantics idempotent:
  - `patch_copyfile()` stores `shutil._orig_copyfile` only when needed (`speedcopy/copyfile.py`).
  - `unpatch_copyfile()` restores from `_orig_copyfile`.
- Preserve special-file protections in both backends:
  - Named pipes must raise `shutil.SpecialFileError` (`speedcopy/win.py`, `speedcopy/posix.py`).
  - Same-file detection must raise `SameFileError`/`shutil.SameFileError`.

## Platform-Specific Rules
### Windows (`speedcopy/win.py`)
- Keep native-call preference: `CopyFile2` first, fallback to `CopyFileW`.
- Preserve long-path + UNC normalization pattern before API call:
  - Normalize to absolute path, then prefix with `\\?\`; convert UNC to `UNC\...` form.
- Do not remove alternate stream skip flag (`0x00008000` in `PARAMS.dwCopyFlags`).
- Keep `ERROR_IO_PENDING` (`997`) treated as success; current behavior intentionally returns `dst`.

### POSIX (`speedcopy/posix.py`)
- Keep filesystem-gated server-side copy path:
  - Attempt ioctl copy only when both source and destination FS are `CIFS`/`SMB2`.
- Preserve fallback order:
  1. `ioctl(... CIFS_IOC_COPYCHUNK_FILE ...)`
  2. `_copyfile_sendfile(...)`
  3. `shutil.copyfileobj(...)`
- Keep symlink behavior parity: when `follow_symlinks=False`, create symlink instead of file copy.

## Style and Tooling Constraints
- Ruff is strict (`[tool.ruff.lint] select = ["ALL"]`) with explicit ignores in `pyproject.toml`; run Ruff after edits.
- Respect `line-length = 79` and existing type-hint style (uses `typing.Union` for old Python compatibility).
- Use `pyproject.toml` as the source of truth for packaging/version constraints.
- Treat `setup.py` as legacy compatibility metadata; do not add new project logic there unless required.

## Testing and Validation Expectations
- Run focused tests in `tests/test_speedcopy.py` for copy and patch/unpatch behavior.
- For packaging-sensitive changes, mimic release workflow expectations:
  - wheel and sdist are both test-installed (`.github/workflows/pythonpublish.yml`).
- If touching platform paths, validate at least the impacted backend and fallback path behavior.

## Change Boundaries
- Do not commit build/cache artifacts (`dist/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`).
- Avoid API changes in `speedcopy/__init__.py` unless explicitly requested.
- Keep benchmark changes isolated to `benchmark.py`; do not couple benchmark-only tweaks into runtime paths.

