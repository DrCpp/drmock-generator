# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
# 
# SPDX-License-Identifier: GPL-3.0-or-later

import clang.cindex
from unittest import mock
import pytest

from drmock import types
from drmock import translator

TYPE = 'std::shared_ptr<T>'
PATH = 'dummy.h'


class TestType:

    @pytest.mark.parametrize('type_, expected', [
        (types.Type(inner=TYPE, const=True), types.Type(inner=TYPE)),
        (types.Type(inner=TYPE, volatile=True), types.Type(inner=TYPE)),
        (types.Type(inner=TYPE, const=True, volatile=True), types.Type(inner=TYPE)),
        (types.Type(inner=TYPE, lvalue_ref=True), types.Type(inner=TYPE)),
        (types.Type(inner=TYPE, rvalue_ref=True), types.Type(inner=TYPE)),
        (types.Type(inner=types.Type(inner=TYPE, const=True), lvalue_ref=True),
         types.Type(inner=TYPE)),
        (types.Type(inner=types.Type(inner=TYPE, const=True), rvalue_ref=True),
         types.Type(inner=TYPE)),
        (types.Type(inner=types.Type(inner=TYPE, volatile=True), lvalue_ref=True),
         types.Type(inner=TYPE)),
        (types.Type(inner=types.Type(inner=TYPE, volatile=True), rvalue_ref=True),
         types.Type(inner=TYPE)),
        (types.Type(inner=types.Type(inner=TYPE, const=True)), types.Type(inner=TYPE)),
    ])
    def test_get_decayed(self, type_, expected):
        assert type_.get_decayed() == expected

    @pytest.mark.parametrize('tokens, expected', [
        ([TYPE], types.Type(inner=TYPE)),
        ([TYPE, '&'], types.Type(inner=TYPE, lvalue_ref=True)),
        ([TYPE, '&&'], types.Type(inner=TYPE, rvalue_ref=True)),
        (['const', TYPE], types.Type(inner=TYPE, const=True)),
        (['const', TYPE, '&'],
         types.Type(inner=types.Type(inner=TYPE, const=True), lvalue_ref=True)),
        (['const', TYPE, '&', '...'],
         types.Type(inner=types.Type(inner=TYPE, const=True), lvalue_ref=True,
                    parameter_pack=True)), ([TYPE, '*'], types.Type(inner=TYPE, pointer=True)),
        ([TYPE, '*', 'const'], types.Type(inner=TYPE, const=True, pointer=True)),
        (['const', TYPE, '*'],
         types.Type(inner=types.Type(inner=TYPE, const=True), pointer=True)),
        ([TYPE, '*', 'const', '&'],
         types.Type(inner=types.Type(inner=TYPE, const=True, pointer=True), lvalue_ref=True)),
        ([TYPE, '*', '&&'],
         types.Type(inner=types.Type(inner=TYPE, pointer=True), rvalue_ref=True)),
        ([TYPE, '*', '&&', '...'],
         types.Type(inner=types.Type(inner=TYPE, pointer=True),
                    rvalue_ref=True,
                    parameter_pack=True))
    ])
    def test_from_tokens(self, tokens, expected):
        assert types.Type.from_tokens(tokens) == expected

    @pytest.mark.parametrize('type_, expected', [
        (types.Type(inner='T'), 'T'), (types.Type(inner='T', lvalue_ref=True), 'T &'),
        (types.Type(inner='T', rvalue_ref=True), 'T &&'),
        (types.Type(inner='T', const=True), 'const T'),
        (types.Type(inner=types.Type(inner='T', const=True), lvalue_ref=True), 'const T &'),
        (types.Type(inner=types.Type(inner='T', const=True), lvalue_ref=True,
                    parameter_pack=True), 'const T & ...'),
        (types.Type(inner='T', pointer=True), 'T *'),
        (types.Type(inner='T', const=True, pointer=True), 'T * const'),
        (types.Type(inner=types.Type(inner='T', const=True), pointer=True), 'const T *'),
        (types.Type(inner=types.Type(inner='T', const=True, pointer=True),
                    lvalue_ref=True),
         'T * const &'),
        (types.Type(inner=types.Type(inner='T', pointer=True),
                    rvalue_ref=True),
         'T * &&'),
        (types.Type(inner=types.Type(inner='T', pointer=True),
                    rvalue_ref=True,
                    parameter_pack=True),
         'T * && ...'),
        (types.Type(inner=types.Type(inner='T', const=True),
                    pointer=True,
                    const=True),
         'const T * const')
    ])
    def test__str__(self, type_, expected):
        assert str(type_) == expected

    @pytest.mark.parametrize('tokens, const, volatile, spelling, expected', [
        ([TYPE], False, False, '', types.Type(inner=TYPE)),
        ([TYPE, '&'], False, False, 'foo', types.Type(inner=TYPE, lvalue_ref=True)),
        ([TYPE, '&&'], False, False, '', types.Type(inner=TYPE, rvalue_ref=True)),
        (['const', TYPE], True, False, '', types.Type(inner=TYPE, const=True)),
        (['const', TYPE, '&'], False, False, 'foo',
         types.Type(inner=types.Type(inner=TYPE, const=True), lvalue_ref=True)),
        (['const', TYPE, '&', '...'], False, False, 'foo',
         types.Type(inner=types.Type(inner=TYPE, const=True), lvalue_ref=True,
                    parameter_pack=True)),
        ([TYPE, '*'], False, False, '', types.Type(inner=TYPE, pointer=True)),
        ([TYPE, '*', 'const'], True, False, '', types.Type(inner=TYPE, const=True, pointer=True)),
        (['const', TYPE, '*'], False, False, '',
         types.Type(inner=types.Type(inner=TYPE, const=True), pointer=True)),
        ([TYPE, '*', 'const', '&'], False, False, 'foo',
         types.Type(inner=types.Type(inner=TYPE, const=True, pointer=True), lvalue_ref=True)),
        ([TYPE, '*', '&&'], False, False, 'foo',
         types.Type(inner=types.Type(inner=TYPE, pointer=True), rvalue_ref=True)),
        ([TYPE, '*', '&&', '...'], False, False, '',
         types.Type(inner=types.Type(inner=TYPE, pointer=True),
                    rvalue_ref=True,
                    parameter_pack=True)),
        (['const', TYPE, '*', 'const'], True, False, 'foo',
         types.Type(inner=types.Type(inner=TYPE, const=True),
                    pointer=True,
                    const=True))
    ])
    def test_from_node(self, const, volatile, tokens, spelling, expected, mocker):
        # Mock ``types`` to separate clang and drmock functionality.
        c = mocker.Mock()
        c.get_tokens = mocker.Mock()
        c.get_tokens.return_value = tokens
        c.cursor.spelling = spelling
        c.cursor.type.is_const_qualified.return_value = const
        c.cursor.type.is_volatile_qualified.return_value = volatile

        assert types.Type.from_node(c) == expected


class TestTemplateDecl:

    @pytest.mark.parametrize('params, expected', [
        (['T'], ['T']),
        (['T1', 'T2', 'T3'], ['T1', 'T2', 'T3']),
        (['T1', 'T2', '... Ts'], ['T1', 'T2', 'Ts ...'])
    ])
    def test_get_args(self, params, expected):
        template = types.TemplateDecl(params)
        assert template.get_args() == expected

    @pytest.mark.parametrize('params, expected', [
        (['T'], 'template<typename T>'),
        (['T1', 'T2', 'T3'], 'template<typename T1, typename T2, typename T3>'),
        (['T1', 'T2', '... Ts'], 'template<typename T1, typename T2, typename ... Ts>')
    ])
    def test__str__(self, params, expected):
        template_decl = types.TemplateDecl(params)
        assert str(template_decl) == expected

    def test_from_node(self, mocker):
        template_type_param1 = mocker.Mock(get_tokens=mocker.Mock(return_value=['typename', 'T']),
                                           cursor=mocker.Mock(
            kind=clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER),
            spec=translator.Node)
        template_type_param2 = mocker.Mock(get_tokens=mocker.Mock(return_value=['typename', '...', 'Ts']),
                                           cursor=mocker.Mock(
            kind=clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER),
            spec=translator.Node)
        decoy = mocker.Mock(cursor=mocker.Mock(kind=clang.cindex.CursorKind.CXX_METHOD),
                            spec=translator.Node)
        parent = mocker.Mock(
            get_children=mocker.Mock(
                return_value=[
                    template_type_param1,
                    decoy,
                    template_type_param2]))
        template_decl = types.TemplateDecl.from_node(parent)
        assert template_decl._params == ['T', '... Ts']


class TestMethod:

    @pytest.mark.parametrize('name, expected', [
        ('operator<=>', 'operatorSpaceShip'),
        ('operator->*', 'operatorPointerToMember'),
        ('operatorco_await', 'operatorCoAwait'),
        ('operator==', 'operatorEqual'),
        ('operator!=', 'operatorNotEqual'),
        ('operator<=', 'operatorLesserOrEqual'),
        ('operator>=', 'operatorGreaterOrEqual'),
        ('operator<<', 'operatorStreamLeft'),
        ('operator>>', 'operatorStreamRight'),
        ('operator&&', 'operatorAnd'),
        ('operator||', 'operatorOr'),
        ('operator++', 'operatorIncrement'),
        ('operator--', 'operatorDecrement'),
        ('operator->', 'operatorArrow'),
        ('operator()', 'operatorCall'),
        ('operator[]', 'operatorBrackets'),
        ('operator+', 'operatorPlus'),
        ('operator-', 'operatorMinus'),
        ('operator*', 'operatorAst'),
        ('operator/', 'operatorDiv'),
        ('operator%', 'operatorModulo'),
        ('operator^', 'operatorCaret'),
        ('operator&', 'operatorAmp'),
        ('operator|', 'operatorPipe'),
        ('operator~', 'operatorTilde'),
        ('operator!', 'operatorNot'),
        ('operator=', 'operatorAssign'),
        ('operator<', 'operatorLesser'),
        ('operator>', 'operatorGreater'),
        ('operator,', 'operatorComma'),
        ('PascalCaseOperator', 'PascalCaseOperator'),
        ('camelCaseOperator', 'camelCaseOperator'),
        ('snake_case_operator', 'snake_case_operator'),
    ])
    def test_mangled_name(self, name, expected):
        method = types.Method(name)
        assert method.mangled_name() == expected

    @pytest.mark.parametrize('method, expected', [
        (types.Method('foo', params=[], return_type='void'), 'void foo();'),
        (types.Method('bar',
                      params=[types.Type('int'),
                              types.Type('float'),
                              types.Type(inner='std::vector<double>', const=True, pointer=True)],
                      const=True,
                      virtual=True),
         'virtual void bar(int, float, std::vector<double> * const) const;'),
        (types.Method('baz',
                      return_type='T&',
                      params=['int', 'float', 'std::vector<double> * const'],
                      volatile=True,
                      virtual=True,  # FIXME This must be set! See also src/drmock/types.py.
                      pure_virtual=True),
         'virtual T& baz(int, float, std::vector<double> * const) volatile = 0;'),
        (types.Method('quz',
                      return_type='T1',
                      params=['T2', 'Ts...'],
                      template=types.TemplateDecl(['T1', 'T2', '... Ts']),
                      body='return T1{};'),
         'template<typename T1, typename T2, typename ... Ts>\nT1 quz(T2, Ts...)\n{\n  return T1{};\n}')
    ])
    def test__str__(self, method, expected):
        assert str(method) == expected

    # NOTE To prevent making the test even more complicated, we test
    # ``Method.from_node`` against the translator's function instead of
    # its expected behavior.
    @pytest.mark.parametrize('source, expected', [
        ('class Dummy { void f(); };',
         types.Method(name='f', params=[], return_type=types.Type('void'))),
        ('class Dummy { int f(int, float, double); };',
         types.Method(name='f', params=[types.Type('int'), types.Type('float'), types.Type('double')],
                      return_type=types.Type('int'))),
        ('class Dummy { const int& operator[](int) const volatile noexcept; };',
         types.Method(name='operator[]', params=[types.Type('int')],
                      return_type=types.Type(inner=types.Type('int', const=True), lvalue_ref=True),
                      const=True, volatile=True, noexcept=True, operator=True)),
        ('class Dummy { virtual void f(); };',
         types.Method(name='f', params=[], return_type=types.Type('void'), virtual=True)),
        ('class Dummy { virtual void f() const volatile noexcept = 0; };',
         types.Method(name='f', params=[], return_type=types.Type('void'),
                      const=True, volatile=True, noexcept=True, virtual=True, pure_virtual=True)),
        ('class Base {\n'
         '  virtual void f() const noexcept = 0;\n'
         '};\n'
         'class Derived : public Base {\n'
         '  virtual void f() const noexcept override;\n'
         '};',
         types.Method(name='f', params=[], return_type=types.Type('void'),
                      const=True, noexcept=True, override=True, virtual=True)),
        ('template<typename T> class Dummy { virtual void f(const T*const) = 0; };',
         types.Method(name='f', params=[types.Type(inner=types.Type(inner='T', const=True),
                                                   pointer=True,
                                                   const=True)],
                      virtual=True, pure_virtual=True)),
        (
            'class _ { virtual void f() const& = 0; };',
            types.Method(name='f', params=[], const=True, lvalue=True, pure_virtual=True, virtual=True)
        ),
        (
            'class _ { virtual void f() && noexcept = 0; };',
            types.Method(name='f', params=[], noexcept=True, rvalue=True, pure_virtual=True, virtual=True)
        ),
    ])
    def test_from_node(self, set_library_file, source, expected):
        root = translator.translate(PATH, source, ['--std=c++11'])
        node = root.get_children()[-1]  # Last class declared in ``source``.
        cxx_method = next(each for each in node.get_children()
                          if each.cursor.kind == clang.cindex.CursorKind.CXX_METHOD)
        m = types.Method.from_node(cxx_method)
        assert m == expected


class TestVariable:

    @pytest.mark.parametrize(
        'variable, expected', [
            (types.Variable('parameter_count', 'int', [], False), 'int parameter_count{};'),
            (
                types.Variable('ptr', 'std::shared_ptr<T>', ['t1', 't2'],
                               True), 'mutable std::shared_ptr<T> ptr{t1, t2};')
        ])
    def test__str__(self, variable, expected):
        assert str(variable) == expected


class TestClass:

    @pytest.mark.parametrize('name, enclosing_namespace, template_args, expected', [
        ('Example', ['outer', 'inner'], None, 'outer::inner::Example'),
        ('vector', ['std'], ['T', 'Allocator'], 'std::vector<T, Allocator>'),
        ('global', [], ['T'], 'global<T>')
    ])
    def test_full_name(self, name, enclosing_namespace, template_args, expected, mocker):
        if template_args:
            template = mocker.Mock()
            template.get_args.return_value = template_args
        else:
            template = None
        class_ = types.Class(name, enclosing_namespace=enclosing_namespace, template=template)
        assert class_.full_name() == expected

    @pytest.mark.parametrize('class_, expected', [
        (types.Class('Dummy', members=[types.Method('f1', const=True, volatile=True),
                                       types.TypeAlias('value_type1', 'T'),
                                       types.Method('f2', virtual=True),
                                       types.Variable('field', 'int'),
                                       types.Method('f3', const=True, override=True),
                                       types.Method(
            'f1', params=['int'], virtual=True, pure_virtual=True),
            types.TypeAlias('value_type2', 'T', types.TemplateDecl(['T']))]),
            [types.TypeAlias('value_type1', 'T'), types.TypeAlias('value_type2', 'T', types.TemplateDecl(['T']))])
    ])
    def test_get_type_aliases(self, class_, expected):
        assert class_.get_type_aliases() == expected

    @pytest.mark.parametrize('class_, expected', [
        (types.Class('Dummy', members=[types.Method('f1', const=True, volatile=True),
                                       types.TypeAlias('value_type1', 'T'),
                                       types.Method('f2', virtual=True),
                                       types.Variable('field', 'int'),
                                       types.Method('f3', const=True, override=True),
                                       types.Method(
            'f1', params=['int'], virtual=True, pure_virtual=True),
            types.TypeAlias('value_type2', 'T', types.TemplateDecl(['T']))]),
            False),
        (types.Class('Dummy', members=[types.Method('f1', const=True, volatile=True),
                                       types.Method('f2', virtual=True),
                                       types.Variable('field', 'int'),
                                       types.Method('f3', const=True, override=True),
                                       types.Method('f1', params=['int'], virtual=True, pure_virtual=True)]),
         True),
        (types.Class('Dummy',
                     members=[types.Method('f1', const=True, volatile=True),
                              types.Method('f2', virtual=True),
                              types.Variable('field', 'int'),
                              types.Method('f3', const=True, override=True),
                              types.Method('f1', params=['int'], virtual=True, pure_virtual=True)],
                     template=types.TemplateDecl(['T', '... Ts'])),
         False)
    ])
    def test_explicit_instantiation_allowed(self, class_, expected):
        assert class_.explicit_instantiation_allowed() == expected

    @pytest.mark.parametrize('class_, expected', [
        (types.Class('Dummy', members=[types.Method('f1', const=True, volatile=True),
                                       types.TypeAlias('value_type1', 'T'),
                                       types.Method('f2', virtual=True),
                                       types.Variable('field', 'int'),
                                       types.Method('f3', const=True, override=True),
                                       types.Method(
            'f1', params=['int'], virtual=True, pure_virtual=True),
            types.TypeAlias('value_type2', 'T', types.TemplateDecl(['T']))]),
            [types.Method('f2', virtual=True), types.Method('f1', params=['int'], virtual=True, pure_virtual=True)])])
    def test_get_virtual_methods(self, class_, expected):
        assert class_.get_virtual_methods() == expected

    # NOTE To prevent making the test even more complicated, we test
    # ``TypeAlias.from_node`` against the translator's function instead
    # of its expected behavior. We're not mocking the members for the
    # same reason, so we're also testing against the functionality of
    # the XXX.from_node classmethods.
    #
    # NOTE As mentioned in the documentation of
    # ``types.Class.from_node``, the class is not completely
    # transcribed. For example, the field ``T value`` is skipped.
    @pytest.mark.parametrize('source, index, members, q_object, parent, template', [
        ('class A {};', 0, [], False, None, None),
        ('class Base {};\n'
         'template<typename T, typename... Ts>\n'
         'class Derived : public Base {\n'
         '  int Q_OBJECT;\n'  # Assuming that class is correctly pre-processed!
         'public:\n'
         '  using value_type = T;\n'
         '  Derived();\n'
         '  ~Derived() = default;\n'
         'protected:\n'
         '  void f();\n'
         'private:\n'
         '  T value{};\n'
         '};\n',
         1,
         [types.TypeAlias('value_type', 'T'), types.Method('f', access='protected')],
         True, None, types.TemplateDecl(['T', '... Ts']))
    ])
    def test_from_node(self,
                       source,
                       index,
                       members,
                       q_object,
                       parent,
                       template):
        root = translator.translate(PATH, source, ['--std=c++11'])
        node = root.get_children()[index]
        class_ = types.Class.from_node(node)
        assert class_.members == members
        assert class_.q_object == q_object
        assert class_.parent == parent
        assert class_.template == template

    @pytest.mark.parametrize('class_, expected', [
        (types.Class(name='A'),
         'class A\n'
         '{\n'
         '};'),
        (types.Class(name='B', enclosing_namespace=['outer', 'inner']),
         'namespace outer { namespace inner {\n'
         '\n'
         'class B\n'
         '{\n'
         '};\n'
         '\n'
         '}} // namespace outer::inner'),
        (types.Class(name='C', members=[mock.Mock(__str__=mock.Mock(return_value='T value_;'),
                                                  access='private'),
                                        mock.Mock(__str__=mock.Mock(return_value='void f();'),
                                                  access='public'),
                                        mock.Mock(__str__=mock.Mock(return_value='virtual void g();'),
                                                  access='protected')]),
         'class C\n'
         '{\n'
         '  T value_;\n'
         '\n'
         'public:\n'
         '  void f();\n'
         '\n'
         'protected:\n'
         '  virtual void g();\n'
         '};'),
        (types.Class(name='Derived',
                     template='template<typename T, typename... Ts>',
                     members=[mock.Mock(__str__=mock.Mock(return_value='T value_;'),
                                        access='public')],
                     final=True,
                     q_object=True,
                     parent='Base'),
         'template<typename T, typename... Ts>\n'
         'class Derived final : public Base\n'
         '{\n'
         '  Q_OBJECT\n'
         '\n'  # FIXME This isn't pretty!
         '\n'
         'public:\n'
         '  T value_;\n'
         '};')
    ])
    def test__str__(self, class_, expected):
        assert str(class_) == expected


class TestTypeAlias:

    # NOTE To prevent making the test even more complicated, we test
    # ``TypeAlias.from_node`` against the translator's function instead
    # of its expected behavior.
    @pytest.mark.parametrize('source, expected', [
        ('using T = int;', types.TypeAlias('T', 'int')),
        ('template<typename T> using T = const int* const;',
         types.TypeAlias('T', 'const int *const', types.TemplateDecl(['T'])))
    ])
    def test_from_node(self, source, expected):
        root = translator.translate(PATH, source, ['--std=c++11'])
        node = root.get_children()[0]
        assert types.TypeAlias.from_node(node) == expected

    @pytest.mark.parametrize('type_alias, expected', [
        (types.TypeAlias('value_type', 'int', None), 'using value_type = int;'),
        (types.TypeAlias('vector_type', 'std::vector<T>', types.TemplateDecl(['T'])),
         'template<typename T> using vector_type = std::vector<T>;'),
    ])
    def test__str__(self, type_alias, expected):
        assert str(type_alias) == expected
