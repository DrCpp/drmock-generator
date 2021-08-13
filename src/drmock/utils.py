# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any, Sequence

import re

INDENT_WIDTH = 2


def template(params: Sequence[Any]) -> str:
    """Join sequence in angled braces."""
    return "<" + ", ".join(str(each) for each in params) + ">"


def swap(regex: str, dst: str, src: str) -> str:
    """Capture ``src`` with ``regex`` and replace every substring
    `r'\1'` in ``dst`` with the content of the first capture group.

    Raises:
        IndexError if ``src`` doesn't match ``regex`` and
        ValueError if ``regex`` doesn't match ``src``.

    Example:
        >>> regex = r'[0-9]([a-z])foo'
        >>> dst = r'foo\1'
        >>> x = '4barfooo'
        >>> swap(regex, dst, x)  # "foobar"
    """
    if r"\1" not in dst:
        return dst

    # Find the capture group's match; raise if there is no match.
    match = re.match(regex, src)
    if not match:
        raise ValueError(f"{src} doesn't match {regex}.")
    inner = match.group(1)
    result = dst.replace(r"\1", inner)
    return result


def split_by_condition(pred, seq: Sequence[_T]) -> list[list[_T]]:
    """Split ``seq`` into lists of equivalence classes.

    Args:
        pred:
            The predicate which sorts the sequence into equivalence
            classes
        seq:
            The sequence to split

    Returns:
        A list which contains the equivalence classes as lists
    """
    # Get values in order of occurence.
    values = []
    for each in seq:
        val = pred(each)
        if val not in values:
            values.append(val)
    return [[each for each in seq if pred(each) == val] for val in values]


def filter_duplicates(it: Iterator[_T]) -> list[_T]:
    """Collect items of iterator without duplicates."""
    return list(dict.fromkeys(it))


def indent(value: str, depth: int = 1, width: int = INDENT_WIDTH) -> str:
    """Indent a string according to depth.

    Args:
        value: The string to indent
        depth: The depth of the string (number of tabs/indents)
        width: Indent width
    """
    result = value
    result = depth * width * " " + result
    result = result.replace("\n", "\n" + depth * width * " ")
    return result


class DrMockRuntimeError(Exception):
    pass
