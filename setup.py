from setuptools import setup, find_packages
from os import path
from io import open


here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(name='speedcopy',
      version='1.0.0',
      description=('Windows xcopy patch for shutil.copyfile'
                   ', based on pyfastcopy'),
      author='Ondrej Samohel',
      author_email='annatar@annatar.net',
      url='',
      long_description=long_description,
      long_description_content_type='text/markdown',
      packages=find_packages(exclude=['contrib', 'docs', 'tests*'])
      )
