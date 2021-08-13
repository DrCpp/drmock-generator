# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Commandline client for drmock generator."""

from __future__ import annotations

import argparse
import locale
import textwrap
import os
import subprocess
import sys

from drmock import generator
from drmock import utils

_parser = argparse.ArgumentParser(
    description="Create mock object .h and .cpp files",
    formatter_class=argparse.RawTextHelpFormatter,
    epilog=textwrap.dedent(
        """
The .cpp file is saved in the same directory as the .h file.

Always use --flags last! (Due to the fact that some compiler options
start with --.)

The input-class and output-class arguments may be regular expressions.
input-class must match a class in input-path; if multiple matches are
found, the first is chosen. output-class may contain a backreference
(\\1) to a capture group in input-class.

The clang-library-file parameter must either be specified using the
command line interface, or by setting the CLANG_LIBRARY_FILE environment
variable.

Use leading :: with -n to specify a global namespace. Otherwise, the
namespace is relative to the enclosing namespace of the target class.
        """
    ),
)
_parser.add_argument("input_path", help="path to .h file containing the input class")
_parser.add_argument("output_path", help="path to output .h")
# NOTE It's a bit awkward to do the calculation of the mock class'
# name _inside_ the tool, but it's the only place where we have
# access to the mockED class.
_parser.add_argument(
    "--input-class",
    "-i",
    default="(.*)",
    help="name of the input class, default is (.*)",
)
_parser.add_argument(
    "--output-class",
    "-o",
    default=r"Mock\1",
    help="name of the output/mock class, default is Mock\\1",
)
# Mock all public virtual functions by default, unless -a=private
_parser.add_argument(
    "--access",
    "-a",
    default=["public", "protected", "private"],
    help="only mock virtual functions with the specified access specs",
)
_parser.add_argument(
    "--namespace", "-n", default="", help="namespace for mock implementation"
)
# # Mock a selection of virtual functions if -m/--methods=
# _parser.add_argument('--methods', '-m', default=[],
#                      help='only mock specified virtual functions')
_parser.add_argument(
    "--clang-library-file",
    "-l",
    default=os.environ.get("CLANG_LIBRARY_FILE", None),
    help="path to the libclang .dll/.so/.dylib",
)
_parser.add_argument(
    "--controller",
    "-c",
    default="control",
    help="name of controller/diagnostics member",
)
_parser.add_argument(
    "--flags", "-f", nargs=argparse.REMAINDER, default=[], help="the C++ compiler flags"
)


def parse_args(args: list[str]) -> argparse.Namespace:
    args = _parser.parse_args(args)

    # Apply isysroot default on macOS.
    if sys.platform == "darwin" and "-isysroot" not in args.flags:
        tmp = subprocess.check_output(["xcrun", "--show-sdk-path"])
        if sys.stdout.encoding is not None:
            encoding = sys.stdout.encoding
        else:
            encoding = locale.getpreferredencoding()
        sdk = tmp.decode(encoding).rstrip("\n")
        args.flags.append("-isysroot")
        args.flags.append(sdk)

    include = os.environ.get("DRMOCK_GENERATOR_INCLUDE", None)
    if include is not None:
        args.flags.append("-I")
        args.flags.append(include)

    return args


# This method is the entry point of the drmock-generator script.
def main() -> None:
    try:
        args = parse_args(sys.argv[1:])
        # Due to the way that argparse parses args, the need to strip
        # the first compiler flag of whitespace!
        if args.flags:
            args.flags[0] = args.flags[0].lstrip()
        generator.main(args)
    except utils.DrMockRuntimeError as e:  # FIXME _Don't_ print traceback on clang errors, etc.!
        print(f"drmock-generator: error: {e}\n", file=sys.stderr)
        sys.exit(1)
