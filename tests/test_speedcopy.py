import shutil
import speedcopy
import os


def setup_function(function):
    speedcopy.patch_copyfile()


def teadown_function(function):
    speedcopy.unpatch_copyfile()


def test_copy(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "destination"
    with open(src, "wb") as f:
        f.write(os.urandom(5 * 1024 * 1024))
    f.close()

    shutil.copyfile(src.as_posix(), dst.as_posix())

    assert os.path.isfile(dst.as_posix())


def test_patch():
    assert shutil.copyfile == speedcopy.copyfile


def test_unpatch():
    speedcopy.unpatch_copyfile()
    assert shutil.copyfile == shutil._orig_copyfile
