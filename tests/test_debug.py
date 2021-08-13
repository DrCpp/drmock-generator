# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os

import clang.cindex
import pytest

from drmock import _debug
from drmock import translator

PATH = "dummy.h"


@pytest.mark.skip
@pytest.mark.parametrize(
    "source, expected",
    [
        (
            "class A {\n" "  void f(int x, float y) {\n" "    return;\n" "  }\n" "};",
            "CursorKind.TRANSLATION_UNIT\n"
            "    CursorKind.CLASS_DECL\n"
            "        CursorKind.CXX_METHOD\n"
            "            get_tokens(): ['void', 'f', '(', 'int', 'x', ',', 'float', 'y', ')', '{', 'return', ';', '}']\n"
            "            CursorKind.PARM_DECL\n"
            "            CursorKind.PARM_DECL\n"
            "            CursorKind.COMPOUND_STMT\n"
            "                CursorKind.RETURN_STMT\n",
        ),
        (
            "class Base {};\n"
            "\n"
            "template<typename T, typename... Ts>\n"
            "class Derived : public Base {\n"
            "public:\n"
            "  virtual int virtual_method(float, double) const;\n"
            "  virtual void pure_virtual_method() = 0;\n"
            "};",
            "CursorKind.TRANSLATION_UNIT\n"
            "    CursorKind.CLASS_DECL\n"
            "    CursorKind.CLASS_TEMPLATE\n"
            "        CursorKind.TEMPLATE_TYPE_PARAMETER\n"
            "        CursorKind.TEMPLATE_TYPE_PARAMETER\n"
            "        CursorKind.CXX_BASE_SPECIFIER\n"
            "            CursorKind.TYPE_REF\n"
            "                spelling: class Base\n"
            "                type.spelling: Base\n"
            "        CursorKind.CXX_ACCESS_SPEC_DECL\n"
            "        CursorKind.CXX_METHOD\n"
            "            get_tokens(): ['virtual', 'int', 'virtual_method', '(', 'float', ',', 'double', ')', 'const']\n"
            "            CursorKind.PARM_DECL\n"
            "            CursorKind.PARM_DECL\n"
            "        CursorKind.CXX_METHOD\n"
            "            get_tokens(): ['virtual', 'void', 'pure_virtual_method', '(', ')', '=', '0']\n",
        ),
    ],
)
def test_dump_tree(source, expected, capsys, set_library_file):
    index = clang.cindex.Index.create()
    node = translator.translate(PATH, source, ["--std=c++17"])
    _debug.print_tree(node)
    captured = capsys.readouterr()
    assert captured.out == expected
