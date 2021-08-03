<!--
SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann

SPDX-License-Identifier: GPL-3.0-or-later
-->

# drmock generator

![Linux](https://github.com/DrCpp/drmock-generator/actions/workflows/linux.yml/badge.svg)
![Windows](https://github.com/DrCpp/drmock-generator/actions/workflows/windows.yml/badge.svg)
![macOS](https://github.com/DrCpp/drmock-generator/actions/workflows/macos.yml/badge.svg)

`drmock-generator` is a component of the C++ testing/mocking framework
[DrMock](https://github.com/DrCpp/DrMock). It takes a C++ `.h` file as
input and generates the files for a mock implementation of the interface
specified in the original header file, which the DrMock framework then
consumes.

The framework contains a CMake integration of `drmock-generator`. Unless
you're using a different build manager, you will not need to call
`drmock-generator` directly. If you're interested in writing integrations for
other build managers, feel free to contact us for support!


## Installing

Run `pip install .` or `make install` install. Usage requires
`python>=3.7`, `python-clang>=11.0` and `libclang`. Install
`python-clang` via `pip install clang`. For `libclang`:

```
sudo apt-get install libclang-7.0-dev       (on Linux)
choco install llvm                          (on Windows)
```

See [chocolatey.org](https://chocolatey.org) for details. On macOS,
`libclang` is installed by default.


## Using

Type `drmock-generator --help` for instructions. You must pass the path to the
`libclang.dll/.so/.dylib` in one of two ways:

- Set the environment variable `CLANG_LIBRARY_FILE` to the absolute path
  of the `libclang.dll/.so/.dylib`
- Specify the absolute path to the `libclang.dll/.so/.dylib` using the
  `-l` parameter

The following paths are usually correct:

```
/usr/lib/llvm-7/lib/libclang.so                              (on Linux)
C:\Program Files\LLVM\bin\libclang.dll                       (on Windows using choco)
/Library/Developer/CommandLineTools/usr/lib/libclang.dylib   (on macOS)
```

On Windows, if you have trouble including STL headers, you may need to
set the environment variable `DRMOCK_GENERATOR_INCLUDE` to the directory
which contains the C++ headers. `drmock-generator` will then add an
automatics `-I%DRMOCK_GENERATOR_INCLUDE%` flags to the compiler call.


## Testing

To run all tests, call `make`. The environment variable
`CLANG_LIBRARY_FILE` must be set in order to test the `translator`
module.

Due to the irreducible complexity of the output of `drmock-generator`, any
significant changes *should* be tested against the latest version of
test suite of the C++ framework, as well.


## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).


## Developer notes

Details on the interface implemented by output code of `drmock-generator` is
compliant with the specification of the C++ framework. See the
documentation of the main framework for details.
