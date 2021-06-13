# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
# 
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from drmock import utils


@pytest.mark.parametrize('params, expected', [
    (['T1', 'T2', 'T3'], '<T1, T2, T3>'),
    ([], '<>'),
    ([[1, 2], 3], '<[1, 2], 3>')
])
def test_template(params, expected):
    assert utils.template(params) == expected


class TestSwap:
    @pytest.mark.parametrize('regex, dst, src, expected', [
        ('I([A-Z].*)', r'\1Bar', 'IFoo', 'FooBar'),
        (r'\.\.\. (.*)', r'\1 ...', '... Foo', 'Foo ...')
    ])
    def test_success(self, regex, dst, src, expected):
        assert utils.swap(regex, dst, src) == expected

    @pytest.mark.parametrize('regex, dst, src, error', [
        ('I.*', '\\1 ...', 'IFoo', IndexError),  # No capture group in first arg.
        ('I([A-Z].*)', '\\1bar', 'Ifoo', ValueError)  # No match.
    ])
    def test_failure(self, regex, dst, src, error):
        with pytest.raises(error):
            utils.swap(regex, dst, src)


@pytest.mark.parametrize('func, iterator, expected', [
    (lambda each: each[1], ['foo', 'bar', 'foobar', 'baz', 'qux'],
     [['foo', 'foobar'], ['bar', 'baz'], ['qux']]),
    (lambda each: len(each), ['foo', 'bar', 'foobar', 'baz', 'qux'],
     [['foo', 'bar', 'baz', 'qux'], ['foobar']])
])
def test_split_by_condition(func, iterator, expected):
    assert sorted(utils.split_by_condition(func, iterator)) == sorted(expected)


@pytest.mark.parametrize('value, depth, width, expected', [
    ('foo', 2, 3, '      foo'),
    ('foo\n bar', 2, 2, '    foo\n     bar'),
    ('foo\nbar', 0, 3, 'foo\nbar'),
    ('\n\n', 1, 3, '   \n   \n   '),
    ('int val = 123;\nauto ptr = &val;', 1, 2, '  int val = 123;\n  auto ptr = &val;')
])
def test_indent(value, depth, width, expected):
    assert utils.indent(value, depth, width) == expected
