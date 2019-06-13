import sys
import tempfile
import timeit
import os
import collections
from pprint import pprint
import time

FILE_SIZES_MB = tuple(2 ** x for x in range(12))


def generate_file(parent_dir, size_b):
    """ Generate a file, write random data to it, and return its filepath. """
    fd, filepath = tempfile.mkstemp(dir=parent_dir)
    with open(filepath, 'wb') as f:
        f.write(os.urandom(size_b * 1024 * 1024))
    os.close(fd)
    return filepath


if __name__ == "__main__":
    try:
        dir = sys.argv[1]
    except:
        print("pass destination directory as an argument if you want")
        dir = None

    with tempfile.TemporaryDirectory(dir=dir) as tmp_dir:
        print("--- using dir {}".format(tmp_dir))
        data = collections.OrderedDict()
        for file_size_mb in FILE_SIZES_MB:
            print("--- Testing filesize: {} Mb".format(file_size_mb))
            datapoint = []
            try:
                src = generate_file(tmp_dir, file_size_mb)
                dst = "%s.dst" % (src)
                for use_fast_copy in (False, True):
                    print(">>> with%s speedcopy ..." % ("" if use_fast_copy else "out"))
                    v = timeit.repeat(
                        setup=("import shutil; import speedcopy; speedcopy.patch_copyfile(); "
                               "p1 = {}; p2 = {}").format(repr(src), repr(dst)),
                        stmt="shutil.{}(p1, p2)".format(
                            "copyfile" if use_fast_copy else "_orig_copyfile"),
                        number=10 if file_size_mb > 64 else 100,
                        repeat=5
                        )
                    v = min(v)
                    dp = str(v / (10 if file_size_mb >= 64 else 100))
                    print("  - Speed: {}".format(dp))
                    datapoint.append(dp)
                    try:
                        os.remove(dst)
                    except FileNotFoundError:
                        pass
                os.remove(src)
                data[file_size_mb] = tuple(datapoint)
            except OSError as e:
                print("error: {}".format(e))
                raise
    pprint(data)
