# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import re
from typing import Optional

import clang.cindex

from drmock import utils

DIAGNOSTIC_FORMAT_OPTIONS = (clang.cindex.Diagnostic.DisplaySourceLocation
                             | clang.cindex.Diagnostic.DisplayColumn
                             | clang.cindex.Diagnostic.DisplaySourceRanges
                             | clang.cindex.Diagnostic.DisplayOption
                             | clang.cindex.Diagnostic.DisplayCategoryId
                             | clang.cindex.Diagnostic.DisplayCategoryName)

CLASS_CURSORS = {clang.cindex.CursorKind.CLASS_DECL, clang.cindex.CursorKind.CLASS_TEMPLATE}


def set_library_file(file: str) -> None:
    """Args:
        file: path to libclang dynamic library.
    """
    clang.cindex.Config.set_library_file(file)


class Node:
    def __init__(self, cursor: clang.cindex.Cursor, path: str) -> None:
        self.cursor = cursor
        self._path = path

    def get_children(self) -> list[clang.cindex.Cursor]:
        return [Node(each, self._path) for each in self.cursor.get_children()
                if str(each.location.file) == self._path]

    def get_tokens(self) -> list[str]:
        return [each.spelling for each in self.cursor.get_tokens()]

    def find_matching_class(self,
                            regex: str,
                            enclosing_namespace: Optional[list[str]] = None
                            ) -> tuple[Optional[Node], list[str]]:
        if not enclosing_namespace:
            enclosing_namespace = []

        for each in self.get_children():
            if each.cursor.kind == clang.cindex.CursorKind.NAMESPACE:
                enclosing_namespace.append(each.cursor.displayname)
                return each.find_matching_class(regex, enclosing_namespace)
                enclosing_namespace.pop()  # Remove namespace upon leaving the node!
            if each.cursor.kind in CLASS_CURSORS and re.match(regex, each.cursor.spelling):
                return each, enclosing_namespace
        return None, []


def translate_file(path: str, compiler_flags: Optional[list[str]] = None) -> Node:
    with open(path, 'r') as f:
        source = f.read()
    return translate(path, source, compiler_flags)


def translate(path: str, source: str, compiler_flags: Optional[list[str]] = None) -> Node:
    """

    Note: ``path`` need not be a real path, provided that ``source`` is
    specified! Observe that ``path`` is mentioned in the diagnostics.
    """
    if not path:
        raise utils.DrMockRuntimeError(f'Invalid filename: {path}')

    if not compiler_flags:
        compiler_flags = []

    index = clang.cindex.Index.create()
    try:
        tu = index.parse(path, ['-x', 'c++'] + compiler_flags, unsaved_files=[(path, source)])
    except clang.cindex.TranslationUnitLoadError as e:
        raise utils.DrMockRuntimeError(str(e))

    # Check for errors.
    if tu.diagnostics:
        error = 'Clang failed. Details:\n\n'
        error += '\n'.join('\t' + each.format(DIAGNOSTIC_FORMAT_OPTIONS)
                           for each in tu.diagnostics)
        raise utils.DrMockRuntimeError(error)

    return Node(tu.cursor, path)
