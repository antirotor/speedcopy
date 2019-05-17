import shutil
import speedcopy
import os


def setup_function(function):
    speedcopy.patch_copyfile()


def teadown_function(function):
    speedcopy.unpatch_copyfile()


def test_copy(tmpdir):
    src = tmpdir.join("source")
    dst = tmpdir.join("destination")
    with open(str(src), "wb") as f:
        f.write(os.urandom(5 * 1024 * 1024))
    f.close()

    shutil.copyfile(str(src), str(dst))

    assert os.path.isfile(str(dst))


def test_patch():
    assert shutil.copyfile == speedcopy.copyfile


def test_unpatch():
    speedcopy.unpatch_copyfile()
    assert shutil.copyfile == shutil._orig_copyfile
