# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import argparse
import textwrap
import os
import subprocess
import sys


_parser = argparse.ArgumentParser(
    description='Create mock object .h and .cpp files',
    formatter_class=argparse.RawTextHelpFormatter,
    epilog=textwrap.dedent('''
        The .cpp file is saved in the same directory as the .h file.

        The input-class and output-class arguments may be regular
        expressions. input-class must match a class in input-path; if
        multiple matches are found, the first is chosen. output-class
        may contain a backreference (\\1) to a capture group in
        input-class.

        The clang-library-file parameter must either be specified using
        the command line interface, or by setting the CLANG_LIBRARY_FILE
        environment variable.'''))


def parse_args(args, exit_on_error: bool = True) -> argparse.Namespace:
    _parser.add_argument('input_path',
                         help='path to .h file containing the input class')
    _parser.add_argument('output_path',
                         help='path to output .h')
    # NOTE It's a bit awkward to do the calculation of the mock class'
    # name _inside_ the tool, but it's the only place where we have
    # access to the mockED class.
    _parser.add_argument('--input-class', default='(.*)',
                         help='name of the input class, default is (.*)')
    _parser.add_argument('--output-class', default=r'Mock\1',
                         help='name of the output/mock class, default is Mock\\1')
    # Mock all public virtual functions by default, unless -a=private
    _parser.add_argument('--access', '-a', default=['public'],
                         help='only mock virtual functions with the specified access specs')
    # Mock a selection of virtual functions if -m/--methods=
    _parser.add_argument('--methods', '-m', default=[],
                         help='only mock specified virtual functions')

    _parser.add_argument('--clang-library-file',
                         default=os.environ.get('CLANG_LIBRARY_FILE', None),
                         help='path to the libclang .dll/.so/.dylib')

    args, compiler_flags = _parser.parse_known_args(args)

    # Apply isysroot default on macOS.
    if sys.platform == 'darwin' and '-isysroot' not in compiler_flags:
        tmp = subprocess.check_output(['xcrun', '--show-sdk-path'])
        sdk = tmp.decode(sys.stdout.encoding).rstrip('\n')
        compiler_flags.append('-isysroot')
        compiler_flags.append(sdk)

    return args, compiler_flags
