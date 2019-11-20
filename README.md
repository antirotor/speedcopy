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

### Windows

| Filesize | Python | Speedcopy | Factor |
| --- | --- | --- | --- |
| 1 | 0.0797 | 0.0222 | 3.59 |
| 2 | 0.1702 | 0.0254 | 6.69 |
| 4 | 0.3257 | 0.0271 | 12.01 |
| 8 | 0.6729 | 0.0337 | 19.94 |
| 16 | 1.335 | 0.0384 | 34.72 |
| 32 | 2.3612 | 0.0625 | 37.72 |
| 64 | 57.4549 | 0.9758 | 58.88 |
| 128 | 10.9294 | 0.1669 | 65.47 |
| 256 | 20.3843 | 2.276 | 8.96 |
| 512 | 35.9462 | 3.9966 | 8.99 |
| 1024 | 65.6285 | 28.0291 | 2.34 |

### Linux

| Filesize | Python | Speedcopy | Factor |
| --- | --- | --- | --- |
| 1 | 0.0682 | 0.0099 | 6.88 |
| 2 | 0.0894 | 0.0105 | 8.51 |
| 4 | 0.1337 | 0.012 | 11.14 |
| 8 | 0.1922 | 0.0145 | 13.25 |
| 16 | 0.2853 | 0.0193 | 14.78 |
| 32 | 0.4724 | 0.0288 | 16.4 |
| 64 | 8.0071 | 0.4724 | 16.94 |
| 128 | 1.3338 | 0.2311 | 5.77 |
| 256 | 2.6599 | 0.4788 | 5.55 |
| 512 | 5.3798 | 0.9796 | 5.49 |
| 1024 | 10.3328 | 2.9180 | 3.54 |

*Note that Windows and Linux timing do not correlate, they are taken from different systems. Notice the spike on 64 Mb size file on both of them. Also note that these figures are not taken from production grade hardware and setup and can be completely off at other places.*

You can test it yourself with included `benchmark.py` (and this will take some time as values are measured multiple times and then averaged).

## Todo

- Better error handling
- Other platforms support
- Conform behaviour to original `shutil.copyfile()`
- Review benchmark code
