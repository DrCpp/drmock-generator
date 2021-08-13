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

MOCK_OBJECT_NAME = "mock"
SHARED_PTR_PREFIX = "DRMOCK_METHOD_PTR"
STATE_OBJECT_NAME = "DRMOCK_STATE_OBJECT_"
DRMOCK_NAMESPACE = "::drmock"
CONST_ENUM = DRMOCK_NAMESPACE + "::Const"
VOLATILE_ENUM = DRMOCK_NAMESPACE + "::Volatile"
LVALUE_ENUM = DRMOCK_NAMESPACE + "::LValueRef"
RVALUE_ENUM = DRMOCK_NAMESPACE + "::RValueRef"
TYPE_CONTAINER = DRMOCK_NAMESPACE + "::TypeContainer"
PARAMETER_PACK = "... DRMOCK_Ts"
MOVE_IF_NOT_COPY_CONSTRUCTIBLE = DRMOCK_NAMESPACE + "::move_if_not_copy_constructible"
DISPATCH_PREFIX = "DRMOCK_DISPATCH"


def get_overloads_of_class(
    class_: types.Class, access_specs: Iterator[str] = None
) -> list[Overload]:
    """Group method of ``class_`` into ``Overload`` objects.

    Args:
        class_: The class whose methods are grouped
        acccess_specs: Only group method with these access specifiers

    Returns:
        A list with the ``Overload`` objects
    """
    if not access_specs:
        access_specs = ["public"]
    virtual_methods = [
        each for each in class_.get_virtual_methods() if each.access in access_specs
    ]
    collections = utils.split_by_condition(lambda f: f.mangled_name(), virtual_methods)
    return [Overload(class_, each) for each in collections]


class Overload:
    """Represents a C++ method overload.

    All methods are assumed to be _non-template_!
    """

    def __init__(self, parent: types.Class, methods: Sequence[types.Method]) -> None:
        self._parent = parent
        self._methods = methods

    def generate_getter(self) -> types.Method:
        """Generate the overload's template getter method."""
        f = self._methods[0]  # Representative of the overload.
        result = types.Method("f")  # Use temporary dummy name for initialization!
        result.name = f.mangled_name()
        result.return_type = types.Type.from_spelling("auto &")

        dispatch = []
        # If all methods have the same parameter types, then these must
        # automatically be passed as arguments to the dispatch call.
        # NOTE When using strings, spelling differences between equal
        # types (``T *`` vs. ``T*``) can cause this part to malfunction.
        if (
            self._all_same_params()
        ):  # Not overloaded or the only difference is cv-qualifiers!
            dispatch += copy.deepcopy(f.params)
        if self._overloaded():
            # If the overloads differ in their params, then the
            # PARAMETER_PACK serves as leading part of the
            # dispatch template and holds the parameter types (and maybe
            # the qualifiers). If the overloads differ only in their
            # qualifiers, then the PARAMETER_PACK serves as the tail end
            # of the dispatch template, following the function
            # parameters added in the if-branch above.
            result.template = types.TemplateDecl([PARAMETER_PACK])
            dispatch += result.template.get_args()

        # If all methods have the same qualifier, they may be
        # automatically passed to the dispatch method.
        if self._all_same_qualifiers():
            if all(each.const for each in self._methods):
                dispatch.append(CONST_ENUM)
            if all(each.lvalue for each in self._methods):
                dispatch.append(LVALUE_ENUM)
            if all(each.rvalue for each in self._methods):
                dispatch.append(RVALUE_ENUM)

        result.body = (
            f"return {_dispatch_name(f.mangled_name())}("
            + TYPE_CONTAINER
            + utils.template(dispatch)
            + "{});"
        )
        result.access = "public"
        return result

    def generate_shared_ptrs(self) -> list[types.Variable]:
        """Generate the overload's ``shared_ptr<Method>`` objects."""
        result = []
        for i, f in enumerate(self._methods):
            template_args = [self._parent.full_name(), f.return_type]
            template_args.extend(each.get_decayed() for each in f.params)

            value_type = "::drmock::Method" + utils.template(template_args)
            ptr = f'std::make_shared<{value_type}>("{f.name}", {STATE_OBJECT_NAME})'
            shared_ptr = types.Variable(
                name=_shared_ptr_name(f.mangled_name(), i),
                type=f"std::shared_ptr<{value_type}>",
                default_args=[ptr],
                access="private",
            )
            result.append(shared_ptr)
        return result

    def generate_dispatch_methods(self) -> list[types.Method]:
        """Generate the overload's dispatch methods."""
        result = []
        for i, f in enumerate(self._methods):
            dispatch = types.Method("f")  # Temporary name for init.
            dispatch.name = _dispatch_name(f.mangled_name())
            dispatch.return_type = types.Type("auto", lvalue_ref=True)

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
            dispatch.params = [
                types.Type(TYPE_CONTAINER + utils.template(template_args))
            ]
            dispatch.body = "return *" + _shared_ptr_name(f.mangled_name(), i) + ";"
            dispatch.access = "private"
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
            impl.params = [
                f"{each} a{i}" for i, each in enumerate(f.params)
            ]  # (Add parameter names!) # noqa: E501

            # If the method is not overloaded, the correct template
            # arguments are automatically used, and need not be manually
            # inserted.
            dispatch_call = self._generate_access(f)
            dispatch_call += (
                ".call("
                + ", ".join(
                    _unpack_and_move(f"a{i}", each) for i, each in enumerate(f.params)
                )
                + ");"
            )

            # If ``f`` is non-void, then the result of the call must be
            # forwarded.
            impl.body = ""  # Reset body!
            if f.return_type == types.Type("void"):
                impl.body += dispatch_call
            else:
                impl.body += f"auto& result = *{dispatch_call}\n"
                impl.body += f"return std::forward<{f.return_type}>({MOVE_IF_NOT_COPY_CONSTRUCTIBLE}(result));"  # noqa: E501

            impl.access = "public"

            result.append(impl)

        return result

    def generate_set_parent(self) -> list[str]:
        """For each function, return a C++ statement to set the parent
        class."""
        return [
            self._generate_access(each) + ".parent(this);" for each in self._methods
        ]

    def _overloaded(self) -> bool:
        """Check if ``self`` is a proper overload (with at least two
        methods)."""
        return len(self._methods) > 1

    def _all_same_params(self) -> bool:
        """Check if all overloads differ only by qualifier."""
        params = self._methods[0].params
        return all(elem.params == params for elem in self._methods)

    def _all_same_qualifiers(self) -> bool:
        f = self._methods[0]
        qualifiers = (f.const, f.lvalue, f.rvalue)
        return all(
            (elem.const, elem.lvalue, elem.rvalue) == qualifiers
            for elem in self._methods
        )

    def _generate_access(self, f: types.Method) -> str:
        """Return code for accessing method ptr from mock object.

        Args:
            f: The method object
            overload: True if ``f`` is overloaded
            const: True if all overloads of ``f`` are const-qualified
            ref: True if all overloads of ``f`` are ref-qualified
        """
        if self._overloaded():
            template_args = []
            if not self._all_same_params():
                template_args += copy.deepcopy(f.params)
            if not self._all_same_qualifiers():
                if f.const:
                    template_args.append(CONST_ENUM)
                if f.volatile:
                    template_args.append(VOLATILE_ENUM)
                if f.lvalue:
                    template_args.append(LVALUE_ENUM)
                if f.rvalue:
                    template_args.append(RVALUE_ENUM)
            result = (
                MOCK_OBJECT_NAME
                + ".template "
                + f.mangled_name()
                + utils.template(template_args)
                + "()"
            )
        else:
            result = MOCK_OBJECT_NAME + "." + f.mangled_name() + "()"
        return result


def _shared_ptr_name(mangled_name: str, i: int) -> str:
    return f"{SHARED_PTR_PREFIX}{mangled_name}_{i}"


def _dispatch_name(mangled_name: str) -> str:
    return DISPATCH_PREFIX + mangled_name


def _unpack_and_move(name: str, type_: types.Type):
    # result = name if type_.lvalue_ref else f'std::move({name})'
    template = str(type_).replace("...", "")
    result = f"std::forward<{template}>({name})"
    result += type_.parameter_pack * "..."
    return result
