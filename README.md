<!--
SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann

SPDX-License-Identifier: GPL-3.0-or-later
-->

# drmock generator

![unix](https://github.com/DrCpp/drmock-gen/actions/workflows/unix.yml/badge.svg)
![windows](https://github.com/DrCpp/drmock-gen/actions/workflows/windows.yml/badge.svg)


## Installing

Run `pip install .` or `make install` install. Usage requires
`python-clang>=11.0` and `libclang`. Install `python-clang`
via `pip install clang`. For `libclang`:

```
sudo apt-get install libclang-6.0-dev       (on Linux)
choco install llvm                          (on Windows)
```

See [chocolatey.org](https://chocolatey.org) and [brew.sh](brew.sh) for
details.

## Using

Type `drmock-gen --help` for instructions. You need to point 


## Testing

To run all tests, call `make`. The environment variable
`CLANG_LIBRARY_FILE` must be set in order to test the `translator`
module.
