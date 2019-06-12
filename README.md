speedcopy
=========

[![Build Status](https://travis-ci.com/antirotor/speedcopy.svg?branch=master)](https://travis-ci.com/antirotor/speedcopy)
[![PyPI version](https://badge.fury.io/py/speedcopy.svg)](https://badge.fury.io/py/speedcopy)

Patched python shutil.copyfile using xcopy on windows to accelerate transfer on windows shares.

Using ``xcopy`` on windows to server-side copy on network shares where enabled.

See https://wiki.samba.org/index.php/Server-Side_Copy

It is based on `pyfastcopy` so it should accelerate copying on linux too.

Those are benchmark values based on my local setup:

Windows copy / local storage
----------------------------

| filesize (mb) | python | copy  |
|--------------:|-------:|------:|
| 1             | 0.003  | 0.067 |
| 2             | 0.005  | 0.067 |
| 4             | 0.010  | 0.068 |
| 8             | 0.020  | 0.073 |
| 16            | 0.042  | 0.079 |
| 32            | 0.088  | 0.092 |
| 64            | 1.925  | 1.200 |
| 128           | 0.366  | 0.169 |
| 256           | 0.754  | 0.277 |
| 512           | 1.622  | 0.505 |
| 1024          | 3.567  | 0.910 |
| 2048          | 7.242  | 2.607 |

Windows xcopy / local storage
-----------------------------

| filesize (mb) | python | xcopy |
|--------------:|-------:|------:|
| 1             | 0.003  | 0.135 |
| 2             | 0.005  | 0.134 |
| 4             | 0.010  | 0.136 |
| 8             | 0.019  | 0.140 |
| 6             | 0.039  | 0.144 |
| 32            | 0.087  | 0.158 |
| 64            | 1.884  | 1.858 |
| 128           | 0.360  | 0.240 |
| 256           | 0.774  | 0.335 |
| 512           | 1.612  | 0.561 |
| 1024          | 3.575  | 1.199 |
| 2048          | 6.864  | 2.599 |

Windows xcopy / samba share
---------------------------

| filesize (mb) | python | xcopy  |
|--------------:|-------:|-------:|
| 1             | 0.070  | 0.153  |
| 2             | 0.144  | 0.157  |
| 4             | 0.298  | 0.163  |
| 8             | 0.623  | 0.167  |
| 16            | 1.181  | 0.176  |
| 32            | 2.385  | 0.195  |
| 64            | 49.040 | 2.437  |
| 128           | 8.846  | 0.306  |
| 256           | 17.135 | 2.954  |
| 512           | 30.407 | 4.422  |
| 1024          | 55.591 | 30.331 |
| 2048          | 105.003| 204.680|

There are some spikes I attribute to working load on system I was running benchmark on. You can test it yourself with included `benchmark.py`
