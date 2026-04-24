# speedcopy

[![Build Status](https://travis-ci.com/antirotor/speedcopy.svg?branch=master)](https://travis-ci.com/antirotor/speedcopy)
[![PyPI version](https://badge.fury.io/py/speedcopy.svg)](https://badge.fury.io/py/speedcopy)

Patched python shutil.copyfile using native call `CopyFile2` on windows to accelerate
transfer on windows shares. On Linux, it issues special ioctl command `CIFS_IOC_COPYCHUNK_FILE` to enable server-side copy.

This works only when both source and destination files are on same SMB1(CIFS)/2/3 filesystem.

See https://wiki.samba.org/index.php/Server-Side_Copy

## Installation

Add speedcopy to `PYTHONPATH` or:

```
pip install speedcopy
```

## Usage

If you want to monkeypatch `shutil.copyfile()` then:

```python
import shutil
import speedcopy

speedcopy.patch_copyfile()

# your code ...
shutil.copyfile(src, dst)
```
This will make last call to use speedcopy.

Direct use:
```python
import speedcopy

# some code ...

speedcopy.copyfile(src, dst)
```

There is also debug mode enabled by setting `speedcopy.SPEEDCOPY_DEBUG = True`. This will print more information during runtime.

## Benchmark
You can run benchmark using `benchmark.py` script. It will run copy operations with different file sizes and print the results in a table format.

### Usage
Benchmark can run in two modes: multithreaded and single-threaded. In multithreaded mode, it will run multiple copy operations in parallel using multiple workers. In single-threaded mode, it will run copy operations sequentially.

#### Arguments:
`python benchmark.py PATH [--sizes-mb SIZES_MB] [--repeats REPEATS] [--copies-per-worker COPIES_PER_WORKER] [--workers WORKERS] `

- `PATH`: Path to the directory where the benchmark files will be created and copied. This should be a path on an SMB/CIFS share for accurate results.
- `--sizes-mb`: Comma-separated list of file sizes in MB to test (default: `1,2,4,8,16,32`).
- `--repeats`: Number of times to repeat each copy operation (default: `3`).
- `--copies-per-worker`: Number of copy operations each worker should perform in multithreaded mode (default: `2`).
- `--workers`: Number of worker threads to use in multithreaded mode (default: `4`).

If `workers` is not set or set to `1`, it will run in single-threaded mode.

### Windows

running with `--sizes-mb 1,2,4,8,16,32 --repeats 3 --copies-per-worker 2 --workers 4`

**Multithreaded mode**

| size(MB) | shutil(s) | speedcopy(s) | shutil(MB/s) | speedcopy(MB/s) | gain  |
|----------|-----------|--------------|--------------|-----------------|-------|
| 1        | 0.202     | 0.087        | 39.6         | 92.2            | 2.33x |
| 2        | 0.289     | 0.099        | 55.4         | 161.8           | 2.92x |
| 4        | 0.430     | 0.121        | 74.3         | 263.8           | 3.55x |
| 8        | 0.780     | 0.164        | 82.1         | 389.4           | 4.74x |
| 16       | 1.476     | 0.247        | 86.7         | 517.3           | 5.97x |
| 32       | 2.824     | 0.390        | 90.7         | 655.8           | 7.23x |

overall gain was 5.41x

---

running with `--sizes-mb 1,2,4,8,16,32 --repeats 3`

**Single-threaded mode**

| size(MB) | shutil(s) | speedcopy(s) | shutil(MB/s) | speedcopy(MB/s) | gain   |
|----------|-----------|--------------|--------------|-----------------|--------|
|        1 |    0.160  |     0.052    |        18.7  |          57.5   |  3.07x |
|        2 |    0.220  |     0.062    |        27.3  |         97.1    |  3.56x |
|        4 |    0.317  |     0.073    |        37.8  |        165.2    |  4.37x |
|        8 |    0.554  |     0.121    |        43.3  |        198.6    |  4.58x |
|       16 |    1.426  |     0.151    |        33.6  |        318.2    |  9.46x |
|       32 |    2.059  |     0.193    |        46.6  |        497.6    | 10.67x |

overall gain was 7.27x

### Linux

running with `--sizes-mb 1,2,4,8,16,32 --repeats 3 --copies-per-worker 2 --workers 4`

**Multithreaded mode**

| size(MB) | shutil(s) | speedcopy(s) | shutil(MB/s) | speedcopy(MB/s) | gain   |
|----------|-----------|--------------|--------------|-----------------|--------|
|        1 |    0.095  |        0.025 |        84.6  |           317.6 |  3.75x |
|        2 |    0.172  |        0.025 |        93.0  |           643.8 |  6.92x |
|        4 |    0.326  |        0.027 |        98.2  |          1204.7 | 12.27x |
|        8 |    0.628  |        0.035 |       101.9  |          1822.1 | 17.88x |
|       16 |    1.224  |        0.045 |       104.6  |          2830.2 | 27.07x |
|       32 |    2.430  |        0.063 |       105.3  |          4037.1 | 38.32x |

---

running with `--sizes-mb 1,2,4,8,16,32 --repeats 3`

**Single-threaded mode**

| size(MB) | shutil(s) | speedcopy(s) | shutil(MB/s) | speedcopy(MB/s) | gain   |
|----------|-----------|--------------|--------------|-----------------|--------|
|        1 |    0.047  |        0.011 |        64.2  |           272.8 |  4.25x |
|        2 |    0.084  |        0.012 |        71.7  |           496.4 |  6.93x |
|        4 |    0.151  |        0.013 |        79.7  |           925.0 | 11.61x |
|        8 |    0.281  |        0.014 |        85.3  |          1674.8 | 19.62x |
|       16 |    0.529  |        0.018 |        90.7  |          2725.3 | 30.04x |
|       32 |    1.029  |        0.025 |        93.3  |          3793.4 | 40.64x |

### maOS

*Based on the measured values, there is no significant gain on macOS.
The gain is around 1.05x in multithreaded mode and around 1.5x in single-threaded mode, which is not significant enough.
It is possible that the file server wasn't configured to support server-side copy for
macOS (on samba, you need to have specific options). Even though I've tested the
configuration, and it should be working, it's possible that there is some issue with the setup.*

---
running with `--sizes-mb 1,2,4,8,16,32 --repeats 3 --copies-per-worker 2 --workers 4`

**Multithreaded mode**

| size(MB) | shutil(s) | speedcopy(s) | shutil(MB/s) | speedcopy(MB/s) | gain  |
|----------|-----------|--------------|--------------|-----------------|-------|
| 1        | 0.343     | 0.309        | 23.4         | 25.9            | 1.11x |
| 2        | 0.432     | 0.424        | 37.0         | 37.7            | 1.02x |
| 4        | 0.606     | 0.621        | 52.8         | 51.5            | 0.97x |
| 8        | 0.940     | 0.940        | 68.0         | 68.1            | 1.00x |
| 16       | 1.663     | 1.585        | 77.0         | 80.8            | 1.05x |
| 32       | 3.077     | 2.941        | 83.2         | 87.0            | 1.05x |

---

running with `--sizes-mb 1,2,4,8,16,32 --repeats 3`

**Single-threaded mode**

| size(MB) | shutil(s) | speedcopy(s) | shutil(MB/s) | speedcopy(MB/s) | gain   |
|----------|-----------|--------------|--------------|-----------------|--------|
|        1 |    0.263  |        0.146 |        11.4  |            20.6 |  1.81x |
|        2 |    0.301  |        0.182 |        19.9  |            32.9 |  1.65x |
|        4 |    0.383  |        0.266 |        31.3  |            45.1 |  1.44x |
|        8 |    0.593  |        0.404 |        40.5  |            59.4 |  1.47x |
|       16 |    1.090  |        0.650 |        44.0  |            73.8 |  1.68x |
|       32 |    1.910  |        1.225 |        50.2  |            78.4 |  1.56x |

*Note that Windows, Linux and macOS timings do not correlate, it is taken from different systems.
Also note that these figures are not taken from production grade hardware and setup and can be completely off at other places.*

