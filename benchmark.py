"""Benchmark the speed of the patched copyfile.

Compares it against the original copyfile.
"""
import collections
import contextlib
import os
import pathlib
import sys
import tempfile
import timeit
from pprint import pprint

FILE_SIZES_MB = tuple(2 ** x for x in range(12))


def generate_file(parent_dir: str, size_b: int) -> str:
    """Generate a file, write random data to it, and return its filepath.

    Args:
        parent_dir: Directory to create the file in.
        size_b: Size of the file in megabytes.

    Returns:
        The filepath of the generated file.

    """
    fd, filepath = tempfile.mkstemp(dir=parent_dir)
    pathlib.Path(filepath).write_bytes(os.urandom(size_b * 1024 * 1024))
    os.close(fd)
    return filepath


if __name__ == "__main__":
    try:
        folder = sys.argv[1]
    except (KeyError, IndexError):
        print("pass destination directory as an argument if you want")
        folder = None

    with tempfile.TemporaryDirectory(dir=folder) as tmp_dir:
        print(f"--- using dir {tmp_dir}")
        data = collections.OrderedDict()
        for file_size_mb in FILE_SIZES_MB:
            print(f"--- Testing filesize: {file_size_mb} Mb")
            datapoint = []
            raw_dp = 0
            try:
                src = generate_file(tmp_dir, file_size_mb)
                dst = f"{src}.dst"
                for use_fast_copy in (False, True):
                    print(">>> with%s speedcopy ..." % ("" if use_fast_copy else "out"))  # noqa: E501
                    v = timeit.repeat(
                        setup=("import shutil; import speedcopy; "
                               "speedcopy.patch_copyfile(); "
                               f"p1 = {src!r}; p2 = {dst!r}"),
                        stmt="shutil.{}(p1, p2)".format(
                            "copyfile" if use_fast_copy else "_orig_copyfile"),
                        number=10 if file_size_mb > 64 else 100,  # noqa: PLR2004
                        repeat=5
                        )
                    v = min(v)
                    dp = v / (10 if file_size_mb >= 64 else 100)  # noqa: PLR2004
                    if not use_fast_copy:
                        raw_dp = dp
                        print(f"  - Speed: {dp}")
                    else:
                        speed_up = raw_dp / dp
                        print(f"  - Speed: {dp}")
                        print(f"  - Speedup: {round(speed_up, 2)}x")
                    datapoint.append(str(dp))
                    with contextlib.suppress(FileNotFoundError):
                        os.remove(dst)
                os.remove(src)
                data[file_size_mb] = tuple(datapoint)
            except OSError as e:
                print(f"error: {e}")
                raise
    pprint(data)  # noqa: T203
