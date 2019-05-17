import shutil
import speedcopy
import os


def test_copy(tmp_path):
    src = tmp_path / "source"
    dst = tmp_path / "destination"
    with open(src, "wb") as f:
        f.write(os.urandom(5 * 1024 * 1024))
    f.close()

    shutil.copyfile(src.as_posix(), dst.as_posix())

    assert os.path.isfile(dst.as_posix())
