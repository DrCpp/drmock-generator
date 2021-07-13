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
sudo apt-get install libclang-7.0-dev       (on Linux)
choco install llvm                          (on Windows)
```

See [chocolatey.org](https://chocolatey.org) for details. On macOS, `libclang` is installed by default.


## Using

Type `drmock-gen --help` for instructions. You must pass the path to the `libclang.dll/.so/.dylib` in one of two ways:

- Set the environment variable `CLANG_LIBRARY_FILE` to the absolute path of the `libclang.dll/.so/.dylib`
- Specify the absolute path to the `libclang.dll/.so/.dylib` using the `-l` parameter

The following paths are usually correct:

```
/usr/lib/llvm-7/lib/libclang.so                              (on Linux)
C:\Program Files\LLVM\bin\libclang.dll                       (on Windows using choco)
/Library/Developer/CommandLineTools/usr/lib/libclang.dylib   (on macOS)
```


## Testing

To run all tests, call `make`. The environment variable
`CLANG_LIBRARY_FILE` must be set in order to test the `translator`
module.
