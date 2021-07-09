# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
# 
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os

import clang.cindex
import pytest
from typing import List, Optional

from drmock import utils
from drmock import translator


PATH = 'virtual_file_name.h'


class TestNode:

    @pytest.mark.skip(reason="Can't be tested beyond verifying the method's imperative. Moreover, we're using this method thoroughly in the others tests.")
    def test_get_children(self):
        pass

    @pytest.mark.skip(reason="Can't be tested beyond verifying the method's imperative. Moreover, we're using this method thoroughly in the others tests.")
    def test_get_tokens(self):
        pass

    # NOTE For the sake of simplicity, we're only testing
    # ``find_matching_class_cursor`` against ``translate``. The reason
    # is that mocking an entire tree of translator.Node objects will
    # result in unreadable tests which verify too much imperative and
    # too little function.
    def test_find_matching_class(self, set_library_file):
        source = ('namespace outer {\n'
                  '\n'
                  'class A {};\n'
                  '\n'
                  'namespace inner {\n'
                  '\n'
                  'class _B {};\n'
                  '\n'
                  '}} // namespace outer::inner\n'
                  '\n'
                  'namespace other {\n'
                  '\n'
                  'class _C {};\n'
                  '\n'
                  '} // namespace other')
        root = translator.translate(PATH, source, ['--std=c++11'])
        class_, enclosing_namespace = root.find_matching_class('_[A-Z]')
        assert class_.cursor.spelling == '_B'
        assert enclosing_namespace == ['outer', 'inner']


class TestTranslate:

    def test_class_template(self, set_library_file):
        root = translator.translate(PATH,
                                    'template<typename T, typename... Ts> class X {};',
                                    ['--std=c++17'])

        node = root.get_children()[0]
        assert node.cursor.kind == clang.cindex.CursorKind.CLASS_TEMPLATE
        children = node.get_children()
        assert len(children) == 2

        t1 = children[0]
        assert t1.cursor.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER
        assert [each.spelling for each in t1.cursor.get_tokens()] == ['typename', 'T']

        t2 = children[1]
        assert t1.cursor.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER
        assert [each.spelling for each in t2.cursor.get_tokens()] == ['typename', '...', 'Ts']

    def test_type_alias(self, set_library_file):
        root = translator.translate(PATH, 'using value_type = int;', ['--std=c++11'])

        node = root.get_children()[0]
        assert node.cursor.kind == clang.cindex.CursorKind.TYPE_ALIAS_DECL
        assert node.cursor.spelling == 'value_type'
        assert node.cursor.underlying_typedef_type.spelling == 'int'

    def test_type_alias_template(self, set_library_file):
        root = translator.translate(PATH,
                                    'template<typename T> using value_type = T;',
                                    ['--std=c++11'])

        node = root.get_children()[0]
        assert node.cursor.kind == clang.cindex.CursorKind.TYPE_ALIAS_TEMPLATE_DECL
        children = node.get_children()

        t1 = next(each for each in children
                  if each.cursor.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER)
        assert [each.spelling for each in t1.cursor.get_tokens()] == ['typename', 'T']

        t2 = next(each for each in children
                  if each.cursor.kind == clang.cindex.CursorKind.TYPE_ALIAS_DECL)
        assert t2.cursor.spelling == 'value_type'
        assert t2.cursor.underlying_typedef_type.spelling == 'T'

    @pytest.mark.parametrize('source, spellings, const', [
        ('void f(int);', ['int'], False),
        ('void f(const int);', ['const', 'int'], True),
        ('void f(int const);', ['int'], True),
        ('void f(const float&);', ['const', 'float', '&'], False),
        ('void f(const char* foo);', ['const', 'char', '*', 'foo'], False),
        ('void f(double* const bar);', ['double', '*', 'const', 'bar'], True),
        ('template<typename... Ts> void f(volatile Ts&&... baz);',
         ['volatile', 'Ts', '&&', '...', 'baz'], False),
        ('void f(const int*const);', ['const', 'int', '*'], True),
    ])
    def test_type(self, set_library_file, source, spellings, const):
        root = translator.translate(PATH, source, ['--std=c++11'])

        node = root.get_children()[0]
        t = next(each for each in node.get_children()
                 if each.cursor.kind == clang.cindex.CursorKind.PARM_DECL)
        tokens = [each.spelling for each in t.cursor.get_tokens()]
        assert tokens == spellings
        assert t.cursor.type.is_const_qualified() == const

    # Test auto f() -> decltype(...)
    @pytest.mark.parametrize('source, spelling, params, tokens, const, virtual, pure_virtual, noexcept', [
        ('class Dummy { void f(); };', 'f', [], [
         'void', 'f', '(', ')'], False, False, False, False),
        ('class Dummy { int f(int, float, double); };', 'f', [['int'], ['float'], ['double']], [
         'int', 'f', '(', 'int', ',', 'float', ',', 'double', ')'], False, False, False, False),
        ('class Dummy { const int& operator[](int) const volatile noexcept; };', 'operator[]', [['int']], [
         'const', 'int', '&', 'operator', '[', ']', '(', 'int', ')', 'const', 'volatile', 'noexcept'], True, False, False, True),
        ('class Dummy { virtual void f(); };', 'f', [], [
         'virtual', 'void', 'f', '(', ')'], False, True, False, False),
        ('class Dummy { virtual void f() const volatile noexcept = 0; };', 'f', [], [
         'virtual', 'void', 'f', '(', ')', 'const', 'volatile', 'noexcept', '=', '0'], True, True, True, True),
        ('class Base {\n'
         '  virtual void f() const noexcept = 0;\n'
         '};\n'
         'class Derived : public Base {\n'
         '  virtual void f() const noexcept override;\n'
         '};',
         'f', [], ['virtual', 'void', 'f', '(', ')', 'const', 'noexcept', 'override'], True, True, False, True),
    ])
    def test_cxx_method(self,
                        set_library_file,
                        source,
                        spelling,
                        params,
                        tokens,
                        const,
                        virtual,
                        pure_virtual,
                        noexcept):
        root = translator.translate(PATH, source, ['--std=c++11'])
        node = root.get_children()[-1]  # Last class declared in ``source``.
        cxx_method = next(each for each in node.get_children()
                          if each.cursor.kind == clang.cindex.CursorKind.CXX_METHOD)
        assert cxx_method.cursor.spelling == spelling
        assert [each.get_tokens() for each in cxx_method.get_children()
                if each.cursor.kind == clang.cindex.CursorKind.PARM_DECL] == params
        assert cxx_method.get_tokens() == tokens
        assert cxx_method.cursor.is_const_method() == const
        assert cxx_method.cursor.is_virtual_method() == virtual
        assert cxx_method.cursor.is_pure_virtual_method() == pure_virtual
        assert not noexcept or cxx_method.cursor.exception_specification_kind == clang.cindex.ExceptionSpecificationKind.BASIC_NOEXCEPT

    def test_class(self, set_library_file):
        source = ('class Base {};\n'
                  '\n'
                  'template<typename T, typename... Ts>\n'
                  'class Derived : public Base {\n'
                  'public:\n'
                  '  using value_type = T;\n'
                  '  Derived();\n'
                  '  ~Derived() = default;\n'
                  '  void f();\n'
                  'private:\n'
                  '  T value{};\n'
                  '};')
        root = translator.translate(PATH, source, ['--std=c++11'])

        node1 = root.get_children()[0]  # Base
        assert node1.cursor.kind == clang.cindex.CursorKind.CLASS_DECL

        node2 = root.get_children()[1]  # Derived
        template_type_params = [each.get_tokens() for each in node2.get_children(
        ) if each.cursor.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER]
        assert template_type_params == [['typename', 'T'], ['typename', '...', 'Ts']]

        # Go thru children, starting with the first access spec decl (we're
        # skipping the CXX_BASE_SPECIFIER!).
        offset = next(i for i, elem in enumerate(node2.get_children())
                      if elem.cursor.kind == clang.cindex.CursorKind.CXX_ACCESS_SPEC_DECL)
        children = node2.get_children()[offset:]
        assert len(children) == 7

        # We already know that...
        assert children[0].cursor.kind == clang.cindex.CursorKind.CXX_ACCESS_SPEC_DECL
        assert children[1].cursor.kind == clang.cindex.CursorKind.TYPE_ALIAS_DECL
        assert children[2].cursor.kind == clang.cindex.CursorKind.CONSTRUCTOR
        assert children[3].cursor.kind == clang.cindex.CursorKind.DESTRUCTOR
        assert children[4].cursor.kind == clang.cindex.CursorKind.CXX_METHOD
        assert children[5].cursor.kind == clang.cindex.CursorKind.CXX_ACCESS_SPEC_DECL
        assert children[6].cursor.kind == clang.cindex.CursorKind.FIELD_DECL

    def test_namespace(self, set_library_file):
        source = ('namespace outer {\n'
                  '\n'
                  'class A {};\n'
                  '\n'
                  'namespace inner {\n'
                  '\n'
                  'class B {};\n'
                  '\n'
                  '}} // namespace outer::inner\n'
                  '\n'
                  'namespace other {\n'
                  '\n'
                  'class C {};\n'
                  '\n'
                  '} // namespace other')
        root = translator.translate(PATH, source, ['--std=c++11'])
        assert len(root.get_children()) == 2

        outer = root.get_children()[0]
        assert outer.cursor.kind == clang.cindex.CursorKind.NAMESPACE
        assert outer.cursor.displayname == 'outer'
        other = root.get_children()[1]
        assert other.cursor.kind == clang.cindex.CursorKind.NAMESPACE
        assert other.cursor.displayname == 'other'

        assert len(outer.get_children()) == 2
        a = outer.get_children()[0]
        assert a.cursor.kind == clang.cindex.CursorKind.CLASS_DECL
        assert a.cursor.spelling == 'A'
        inner = outer.get_children()[1]
        assert inner.cursor.kind == clang.cindex.CursorKind.NAMESPACE
        assert inner.cursor.displayname == 'inner'

        assert len(inner.get_children()) == 1
        b = inner.get_children()[0]
        assert b.cursor.kind == clang.cindex.CursorKind.CLASS_DECL
        assert b.cursor.spelling == 'B'

        assert len(other.get_children()) == 1
        c = other.get_children()[0]
        assert c.cursor.kind == clang.cindex.CursorKind.CLASS_DECL
        assert c.cursor.spelling == 'C'

    @pytest.mark.parametrize('source, compiler_flags', [
        pytest.param('template<typename Ts> class A {', None, id='syntax error'),
        ('class A {}', None),
        ('void f(int, float,);', None),
        pytest.param('void f();', ['--foo=bar'], id='unknown option'),
        pytest.param('using value_type = T', ['--std=c++11'], id="unknown type name 'T'")
    ])
    def test_failure(self, source, compiler_flags, set_library_file):
        with pytest.raises(utils.DrMockRuntimeError):
            node = translator.translate(PATH, source, compiler_flags)

    def test_bug_0(self, set_library_file):
        path = 'void_func.h'
        compiler_flags = [
            '--std=c++14',
            '-isysroot',
            '/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk']
        source = '''/* Copyright 2019 Ole Kliemann, Malte Kliemann
                     *
                     * This file is part of DrMock.
                     *
                     * DrMock is free software: you can redistribute it and/or modify it
                     * under the terms of the GNU General Public License as published by
                     * the Free Software Foundation, either version 3 of the License, or
                     * (at your option) any later version.
                     *
                     * DrMock is distributed in the hope that it will be useful, but
                     * WITHOUT ANY WARRANTY; without even the implied warranty of
                     * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
                     * General Public License for more details.
                     *
                     * You should have received a copy of the GNU General Public License
                     * along with DrMock.  If not, see <https://www.gnu.org/licenses/>.
                    */

                    #ifndef DRMOCK_TESTS_MOCKER_IVOIDFUNC_H
                    #define DRMOCK_TESTS_MOCKER_IVOIDFUNC_H

                    #include <vector>

                    namespace outer { namespace inner {

                    class IVoidFunc
                    {
                    public:
                      virtual ~IVoidFunc() = default;

                      virtual void f() = 0;
                    };

                    }} // namespace outer::inner

                    #endif /* DRMOCK_TESTS_MOCKER_IVOIDFUNC_H */'''
        translator.translate(path, source, compiler_flags)
