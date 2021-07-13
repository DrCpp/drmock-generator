# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup


setup(
    name='drmock-generator',
    author='Malte Kliemann, Ole Kliemann',
    version='0.6.0-beta',
    packages=['drmock'],
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'drmock-gen = drmock.commandline:main'
        ]
    },
    include_package_data=True,
    python_requires='>=3.7',
    install_requires=[
        'clang>=11.0',
    ]
)
