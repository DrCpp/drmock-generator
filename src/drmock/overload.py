# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""For mocking overloaded C++ methods."""

from __future__ import annotations

import copy
import dataclasses
from typing import Iterator, Sequence

from drmock import types
from drmock import utils

MOCK_OBJECT_NAME = 'mock'
SHARED_PTR_PREFIX = 'METHODS_DRMOCK_'
STATE_OBJECT_NAME = 'STATE_OBJECT_DRMOCK_'
CONST_ENUM = 'drmock::Const'
VOLATILE_ENUM = 'drmock::Volatile'
LVALUE_ENUM = 'drmock::LValueRef'
RVALUE_ENUM = 'drmock::RValueRef'
TYPE_CONTAINER = 'TypeContainer'
PARAMETER_PACK = '... DRMOCK_Ts'


def get_overloads_of_class(class_: types.Class,
                           access_specs: Iterator[str] = None) -> list[Overload]:
    """Group method of ``class_`` into ``Overload`` objects.

    Args:
        class_: The class whose methods are grouped
        acccess_specs: Only group method with these access specifiers

    Returns:
        A list with the ``Overload`` objects
    """
    if not access_specs:
        access_specs = ['public']
    virtual_methods = [each for each in class_.get_virtual_methods()
                       if each.access in access_specs]
    collections = utils.split_by_condition(lambda f: f.mangled_name(), virtual_methods)
    return [Overload(class_, each) for each in collections]


class Overload:
    """Represents a C++ method overload.

    All methods are assumed to be _non-template_!
    """

    def __init__(self, parent: types.Class, methods: Sequence[types.Method]) -> None:
        self._parent = parent
        self._methods = methods

    def is_overload(self) -> bool:
        """Check if ``self`` is a proper overload (with at least two
        methods)."""
        return len(self._methods) > 1

    def generate_getter(self) -> types.Method:
        """Generate the overload's template getter method."""
        f = self._methods[0]  # Representative of the overload.
        result = types.Method('f')  # Use temporary dummy name for initialization!
        result.name = f.mangled_name()
        result.return_type = types.Type.from_spelling('auto &')

        # If all methods have the same parameter types, then these must
        # automatically be passed as arguments to the dispatch call.
        # NOTE When using strings, spelling differences between equal
        # types (``T *`` vs. ``T*``) can cause this part to malfunction.
        if not self.is_overload():  # all(f.params == each.params for each in self._methods):
            dispatch = f.params[:]
        else:
            result.template = types.TemplateDecl([PARAMETER_PACK])
            dispatch = result.template.get_args()

        # If all methods are const qualified, then the const qualifier
        # must automatically be passed to the dispatch method.
        if all(each.const for each in self._methods):
            dispatch.append(CONST_ENUM)
        if all(each.lvalue for each in self._methods):
            dispatch.append(LVALUE_ENUM)
        if all(each.rvalue for each in self._methods):
            dispatch.append(RVALUE_ENUM)

        result.body = f'return {f.mangled_name()}_dispatch(' + TYPE_CONTAINER + \
            utils.template(dispatch) + '{});'
        result.access = 'public'
        return result

    def generate_shared_ptrs(self) -> list[types.Variable]:
        """Generate the overload's ``shared_ptr<Method>`` objects."""
        result = []
        for i, f in enumerate(self._methods):
            template_args = [self._parent.full_name(), f.return_type]
            template_args.extend(each.get_decayed() for each in f.params)

            value_type = 'Method' + utils.template(template_args)
            ptr = f'std::make_shared<{value_type}>("", {STATE_OBJECT_NAME})'
            shared_ptr = types.Variable(
                name=_shared_ptr_name(f.mangled_name(), i),
                type=f'std::shared_ptr<{value_type}>',
                default_args=[ptr],
                access='private')
            result.append(shared_ptr)
        return result

    def generate_dispatch_methods(self) -> list[types.Method]:
        """Generate the overload's dispatch methods."""
        result = []
        for i, f in enumerate(self._methods):
            dispatch = types.Method('f')  # Temporary name for init.
            dispatch.name = f.mangled_name() + '_dispatch'
            dispatch.return_type = types.Type('auto', lvalue_ref=True)

            # The method's cv qualifiers are stored in the type
            # container's template args, together with the types of the
            # params of ``f``.
            template_args = copy.deepcopy(f.params)
            if f.const:
                template_args.append(types.Type(CONST_ENUM))
            if f.volatile:
                template_args.append(types.Type(VOLATILE_ENUM))
            if f.lvalue:
                template_args.append(types.Type(LVALUE_ENUM))
            if f.rvalue:
                template_args.append(types.Type(RVALUE_ENUM))
            dispatch.params = [types.Type(TYPE_CONTAINER + utils.template(template_args))]
            dispatch.body = 'return *' + _shared_ptr_name(f.mangled_name(), i) + ';'
            dispatch.access = 'private'
            result.append(dispatch)
        return result

    def generate_mock_implementations(self) -> list[types.Method]:
        """Generate the mock implementations of the overload's
        functions."""
        result = []
        for f in self._methods:
            impl = copy.deepcopy(f)  # Keep name, cv qualifiers.
            impl.virtual = False
            impl.pure_virtual = False
            impl.override = True
            impl.params = [f'{each} a{i}' for i, each in enumerate(f.params)]  # (Add parameter names!) # noqa: E501

            # If the method is not overloaded, the correct template
            # arguments are automatically used, and need not be manually
            # inserted.
            dispatch_call = _generate_access(f, self.is_overload())
            dispatch_call += '.call(' + ', '.join(
                _unpack_and_move(f'a{i}', each) for i, each in enumerate(f.params)) + ');'

            # If ``f`` is non-void, then the result of the call must be
            # forwarded.
            impl.body = ''  # Reset body!
            if f.return_type == types.Type('void'):
                impl.body += dispatch_call
            else:
                impl.body += f'auto& result = *{dispatch_call}\n'
                impl.body += f'return std::forward<{f.return_type}>(drmock::moveIfNotCopyConstructible(result));'  # noqa: E501

            impl.access = 'public'

            result.append(impl)

        return result

    def generate_set_parent(self) -> list[str]:
        """For each function, return a C++ statement to set the parent
        class."""
        return [_generate_access(each, self.is_overload()) + '.parent(this);'
                for each in self._methods]


def _shared_ptr_name(mangled_name: str, i: int) -> str:
    return f'{SHARED_PTR_PREFIX}{mangled_name}_{i}'


def _generate_access(f: types.Method, overload: bool) -> str:
    """Return code for accessing method ptr from mock object.

    Args:
        f: The method object
        overload: True if ``f`` is overloaded
    """
    if overload:
        template_args = copy.deepcopy(f.params)
        if f.const:
            template_args.append(CONST_ENUM)
        if f.volatile:
            template_args.append(VOLATILE_ENUM)
        if f.lvalue:
            template_args.append(LVALUE_ENUM)
        if f.rvalue:
            template_args.append(RVALUE_ENUM)
        result = MOCK_OBJECT_NAME + '.template ' + f.mangled_name() \
            + utils.template(template_args) + '()'
    else:
        result = MOCK_OBJECT_NAME + '.' + f.mangled_name() + '()'
    return result


def _unpack_and_move(name: str, type_: types.Type):
    result = name if type_.lvalue_ref else f'std::move({name})'
    result += type_.parameter_pack * '...'
    return result
