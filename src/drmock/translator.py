# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""libclang wrapper module.

This module translates a C++ source into the corresponding AST using the
``translate``. Before calling ``translate``, you must set the path to
the ``libclang.dll/.so/.dylib`` _file_ using ``set_library_file``.
"""

from __future__ import annotations

import re
from typing import Optional

import clang.cindex

from drmock import utils

DIAGNOSTIC_FORMAT_OPTIONS = (
    clang.cindex.Diagnostic.DisplaySourceLocation
    | clang.cindex.Diagnostic.DisplayColumn
    | clang.cindex.Diagnostic.DisplaySourceRanges
    | clang.cindex.Diagnostic.DisplayOption
    | clang.cindex.Diagnostic.DisplayCategoryId
    | clang.cindex.Diagnostic.DisplayCategoryName
)

CLASS_CURSORS = {
    clang.cindex.CursorKind.CLASS_DECL,
    clang.cindex.CursorKind.CLASS_TEMPLATE,
}


def set_library_file(file: str) -> None:
    """Args:
    file: path to libclang dynamic library.
    """
    clang.cindex.Config.set_library_file(file)


class Node:
    """Wrapper class for ``clang.cindex.Cursor`` which tracks file
    membership."""

    def __init__(self, cursor: clang.cindex.Cursor, path: str) -> None:
        """Args:
        cursor: The wrapper cursor
        path: The file that the cursor belongs to
        """
        self._cursor = cursor
        self._path = path

    @property
    def cursor(self) -> clang.cindex.Cursor:
        return self._cursor

    def get_children(self) -> list[Node]:
        """Get all children from the same file."""
        return [
            Node(each, self._path)
            for each in self._cursor.get_children()
            if str(each.location.file) == self._path
        ]

    def get_tokens(self) -> list[str]:
        """Get the cursor's tokens."""
        return [each.spelling for each in self._cursor.get_tokens()]

    def find_matching_class(
        self, regex: str
    ) -> Union[tuple[Optional[Node], list[str]]]:
        """Search the tree under ``self`` for a class whose name matches
        ``regex``.

        Args:
            regex: The regex to match the sought class' name against

        Returns:
            A matching class and the enclosing namespace, or
            ``(None, [])`` if there is no match
        """
        return self._find_matching_class_impl(regex, [])

    def _find_matching_class_impl(
        self, regex: str, enclosing_namespace: list[str]
    ) -> Union[tuple[Optional[Node], list[str]]]:
        for each in self.get_children():
            if each.cursor.kind == clang.cindex.CursorKind.NAMESPACE:
                enclosing_namespace.append(each.cursor.displayname)
                class_, namespace = each._find_matching_class_impl(
                    regex, enclosing_namespace
                )
                if class_ is not None:
                    return class_, namespace
                enclosing_namespace.pop()  # Remove namespace upon leaving the node!
            if each.cursor.kind in CLASS_CURSORS and re.match(
                regex, each.cursor.spelling
            ):
                return each, enclosing_namespace
        return None, []


def translate_file(path: str, compiler_flags: Optional[list[str]] = None) -> Node:
    """Translate the content of ``path`` into its AST.

    Args:
        path: The path to the file
        compiler_flags: A list of compiler flags used for parsing

    Raises:
        clang.cindex.LibclangError:
            If the libclang path is not set or not found (see
            ``set_library_file``)
        utils.DrMockRuntimeError:
            If ``path`` is empty
    """
    with open(path, "r") as f:
        source = f.read()
    return translate(path, source, compiler_flags)


def translate(
    path: str, source: str, compiler_flags: Optional[list[str]] = None
) -> Node:
    """Translate a string with C++ code into its AST.

    Args:
        path: The path of the parsed file
        source: The C++ source
        compiler_flags: A list of compiler flags used for parsing

    Raises:
        clang.cindex.LibclangError:
            If the libclang path is not set or not found (see
            ``set_library_file``)
        utils.DrMockRuntimeError:
            If ``path`` is empty

    Note: The ``path`` parameter is required due to ``clang`` details.
    It need not be a real path, but it must be non-empty. Choosing a
    unique name is useful, as it is used in clang's diagnostics.
    """
    if not path:
        raise utils.DrMockRuntimeError(
            "translate failed: Parameter 'path' is empty. Expected non-empty string"
        )

    if compiler_flags is None:
        compiler_flags = []

    index = clang.cindex.Index.create()
    try:
        tu = index.parse(
            path, ["-x", "c++"] + compiler_flags, unsaved_files=[(path, source)]
        )
    except clang.cindex.TranslationUnitLoadError as e:
        raise utils.DrMockRuntimeError(str(e))

    # Check for errors.
    if tu.diagnostics:
        error = "Clang failed. Details:\n\n"
        error += "\n".join(
            "\t" + each.format(DIAGNOSTIC_FORMAT_OPTIONS) for each in tu.diagnostics
        )
        raise utils.DrMockRuntimeError(error)

    return Node(tu.cursor, path)
