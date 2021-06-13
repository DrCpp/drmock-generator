# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
# 
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from drmock import types
from drmock import generator


@pytest.mark.skip
def test_get_translation_unit():
    path = 'resources/tmp.h'
    with open(path, 'r') as f:
        raw = f.read()
    generator.get_translation_unit('resources/tmp.h', raw)


class TestFriend:

    @pytest.mark.parametrize('friend, expected', [
        (generator.Friend('Foo', 'public'), 'friend class Foo;'),
        (generator.Friend('std::vector<float>', 'private'), 'friend class std::vector<float>;')
    ])
    def test__str__(self, friend, expected):
        assert str(friend) == expected


@pytest.mark.skip
def test_generate_mock_object():
    pass


@pytest.mark.skip
def test_generate_mock_implementation():
    pass


@pytest.mark.parametrize('expr, expected', [
    ('drmock::Method<void>', 'extern template class drmock::Method<void>;'),
    ('Foo<float, std::vector<float>>', 'extern template class Foo<float, std::vector<float>>;'),
])
def test_explicit_instantiation_decl(expr, expected):
    assert generator._explicit_instantiation_decl(expr) == expected


@pytest.mark.parametrize('expr, expected', [
    ('drmock::Method<void>', 'template class drmock::Method<void>;'),
    ('Foo<float, std::vector<float>>', 'template class Foo<float, std::vector<float>>;'),
])
def test_explicit_instantiation_definition(expr, expected):
    assert generator._explicit_instantiation_definition(expr) == expected


@pytest.mark.parametrize('parent, return_type, params, expected', [
    ('Foo', 'void', [], 'drmock::Method<Foo, void>'),
    ('Bar', 'float&', [types.Type(inner='T', const=True), types.Type(
        inner='int', lvalue_ref=True)], 'drmock::Method<Bar, float&, T, int>')
])
def test_generate_method_template(parent, return_type, params, expected):
    method = types.Method(name='f', return_type=return_type, params=params)
    assert generator._generate_method_template(parent, method) == expected
