speedcopy
=========

[![Build Status](https://travis-ci.com/antirotor/speedcopy.svg?branch=master)](https://travis-ci.com/antirotor/speedcopy)
[![PyPI version](https://badge.fury.io/py/speedcopy.svg)](https://badge.fury.io/py/speedcopy)

Patched python shutil.copyfile using native call CopyFileW on windows to accelerate
transfer on windows shares. On Linux, it issues special ioctl command `CIFS_IOC_COPYCHUNK_FILE` to enable server-side copy.

This works only when both files are on same SMB1(CIFS)/2/3 filesystem.

See https://wiki.samba.org/index.php/Server-Side_Copy

Benchmark timings to come ...

You can test it yourself with included `benchmark.py` (and this will take some time as values are measured multiple times).
