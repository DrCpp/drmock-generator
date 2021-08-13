# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""For gathering info about nodes."""

from __future__ import annotations

import functools
from typing import Callable, Optional

import clang.cindex

from drmock import utils

WIDTH = 4


def print_tree(root: translator.Node) -> None:
    def dump_func(node, depth):
        print(_DISPATCH.get(node.cursor.kind, _dump_basic)(node, depth))

    _visit_tree(root, dump_func)


def _visit_tree(
    root: translator.Node,
    func: Callable[[translator.Node], Any],
    depth: Optional[int] = 0,
) -> None:
    func(root, depth)
    for each in root.get_children():
        _visit_tree(each, func, depth + 1)


def _indent(func):
    @functools.wraps(func)
    def new_func(node, depth: Optional[int] = 0):
        result = func(node)
        result = utils.indent(result, depth=depth, width=WIDTH)
        return result

    return new_func


@_indent
def _dump_cxx_method(node: translator.Node) -> None:
    cursor = node.cursor
    lines = []
    lines.append(_dump_basic(node))
    tokens = [each.spelling for each in cursor.get_tokens()]
    lines.append(WIDTH * " " + "get_tokens(): " + str(tokens))
    return "\n".join(lines)


@_indent
def _dump_type_ref(node: translator.Node) -> None:
    lines = [_dump_basic(node)]
    lines.append(WIDTH * " " + "spelling: " + str(node.cursor.spelling))
    lines.append(WIDTH * " " + "type.spelling: " + str(node.cursor.type.spelling))
    return "\n".join(lines)


@_indent
def _dump_basic(node: translator.Node) -> None:
    return str(node.cursor.kind)


_DISPATCH = {
    clang.cindex.CursorKind.CXX_METHOD: _dump_cxx_method,
    clang.cindex.CursorKind.TYPE_REF: _dump_type_ref,
}
