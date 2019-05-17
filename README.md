speedcopy
=========

[![Build status](https://travis-ci.org/antirotor/travis-lab.svg?master)](https://travis-ci.org/antirotor)

Patched python shutil.copyfile using xcopy on windows to accelerate transfer on windows shares.

Using ``xcopy`` on windows to server-side copy on network shares where enabled.

See https://wiki.samba.org/index.php/Server-Side_Copy

It is based on `pyfastcopy` so it should accelerate copying on linux too.
