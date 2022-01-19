# -*- coding: utf-8 -*-
"""Metadata file."""
from setuptools import setup
import os
import imp
from io import open


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

version_file = os.path.abspath("speedcopy/version.py")
version_mod = imp.load_source("version", version_file)
version = version_mod.version

classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.5",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: System :: Filesystems"

]

setup(name='speedcopy',
      version=version,
      description=('Replacement or alternative for python copyfile() '
                   'utilizing server side copy on network shares for faster '
                   'copying.'),
      author='Ondrej Samohel',
      author_email='annatar@annatar.net',
      url='https://github.com/antirotor/speedcopy',
      long_description=long_description,
      long_description_content_type='text/markdown',
      packages=['speedcopy'],
      classifiers=classifiers,
      tests_require=['pytest'],
      )
