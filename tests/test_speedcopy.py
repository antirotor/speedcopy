# -*- coding: utf-8 -*-
"""Tests for speedcopy."""

import shutil
import speedcopy
import os
import pytest


speedcopy.SPEEDCOPY_DEBUG = True
_FILE_SIZE = 5 * 1024 * 1024


def setup_function(function):
    """Test setup."""
    speedcopy.patch_copyfile()


def teadown_function(function):
    """Test teardown."""
    speedcopy.unpatch_copyfile()


def test_copy_abs(tmpdir):
    """Test copy from absolute paths."""
    src = tmpdir.join("source")
    dst = tmpdir.join("destination")
    with open(str(src), "wb") as f:
        f.write(os.urandom(_FILE_SIZE))
    f.close()

    shutil.copyfile(str(src), str(dst))

    assert os.path.isfile(str(dst))


def test_copy_rel(tmpdir):
    """Test copy from relative paths."""
    cwd = os.getcwd()
    os.chdir(str(tmpdir))

    try:
        src = "source"
        dst = "destination"
        with open(str(src), "wb") as f:
            f.write(os.urandom(_FILE_SIZE))
        f.close()

        shutil.copyfile(str(src), str(dst))

        assert os.path.isfile(str(dst))
    finally:
        os.chdir(cwd)


def test_errors(tmpdir):
    """Exception IOError should be raised if file doesn't exist."""
    src = tmpdir.join("source")
    dst = tmpdir.join("destination")

    with pytest.raises(IOError):
        shutil.copyfile(str(src), str(dst))


def test_patch():
    """Test if copyfile is patched."""
    assert shutil.copyfile == speedcopy.copyfile


def test_unpatch():
    """Test if copyfile is restored."""
    speedcopy.unpatch_copyfile()
    assert shutil.copyfile == shutil._orig_copyfile
