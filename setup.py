# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup


setup(name='drmock-generator',
      author='Malte Kliemann, Ole Kliemann',
      version='1.0.0',
      packages=['drmock'],
      package_dir={'': 'src'},
      scripts=['src/drmock-gen'],
      include_package_data=True,
      python_requires='>=3.7',)
