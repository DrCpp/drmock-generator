# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from setuptools import setup

with open('README.md') as readme:
    long_description = readme.read()

setup(
    name='drmock-generator',
    author='Malte Kliemann, Ole Kliemann',
    description='C++ mock object generator',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license='GLP-3.0-or-later',
    version='0.6.0',
    packages=['drmock'],
    package_dir={'': 'src'},
    entry_points={
        'console_scripts': [
            'drmock-generator = drmock.commandline:main'
        ]
    },
    include_package_data=True,
    python_requires='>=3.7',
    install_requires=[
        'clang>=11.0',
    ]
)
