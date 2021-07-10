# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The main generator function."""

from __future__ import annotations

import dataclasses
import os
from typing import Iterable

from drmock import overload
from drmock import types
from drmock import translator
from drmock import utils

MOCK_OBJECT_PREFIX = 'DRMOCK_Object_'
MOCK_OBJECT_ENCLOSING_NAMESPACE = ('drmock', 'mock_implementation')
METHOD_COLLECTION_NAME = 'methods'
METHOD_CPP_CLASS = 'drmock::Method'
INCLUDE_GUARD_PREFIX = 'DRMOCK_MOCK_IMPLEMENTATIONS_'
DRMOCK_INCLUDE_PATH = 'DrMock/'
MACRO_PREFIX = 'DRMOCK_'
FORWARDING_CTOR_TEMPLATE_PARAMS = MACRO_PREFIX + '_FORWARDING_CTOR_TS'


def main(args: str, compiler_flags: list[str]) -> None:
    try:
        with open(args.input_path, 'r') as f:
            old_header = f.read()
    except IOError as e:
        raise utils.DrMockRuntimeError(str(e))

    macros = {'Q_OBJECT'}
    old_header = _hide_macros_from_preprocessor(old_header, macros)
    new_header, new_source = _main_impl(args, compiler_flags, old_header)

    output_path_header = args.output_path
    without_extension, _ = os.path.splitext(output_path_header)
    output_path_source = without_extension + '.cpp'
    try:
        with open(output_path_header, 'w') as f:
            f.write(new_header)
        with open(output_path_source, 'w') as f:
            f.write(new_source)
    except IOError as e:
        raise utils.DrMockRuntimeError(str(e))


def _hide_macros_from_preprocessor(source: str, macros: Iterable[str]) -> str:
    """Hide macros with keywords that drmock recognizes.

    Works by #undef'ing the macro and replacing every occurence by a
    variable declaration.

    Known problems: If ``macros`` is ``['MACRO', 'LONG_MACRO']``, then
    the call will produce unexpected results.
    """

    for each in macros:
        source = source.replace(each, f'#undef {each}\nint {MACRO_PREFIX}{each};')
    return source


def _main_impl(args: str, compiler_flags: list[str], input_header) -> tuple[str, str]:
    if not args.clang_library_file:
        raise utils.DrMockRuntimeError(
            'clang library file path not set. Specify the path to the clang'
            + ' .dll/.so/.dylib using the --clang-library-file command line'
            + ' argument or by setting the environment variable'
            + ' CLANG_LIBRARY_FILE.')
    translator.set_library_file(args.clang_library_file)
    root = translator.translate(args.input_path, input_header, compiler_flags)
    node, enclosing_namespace = root.find_matching_class(args.input_class)

    if not node:
        raise utils.DrMockRuntimeError(
            f"No class matching '{args.input_class}' found in {args.input_path}")
    class_ = types.Class.from_node(node)
    class_.enclosing_namespace = enclosing_namespace

    mock_implementation_name = utils.swap(args.input_class, args.output_class, class_.name)

    mock_object = _generate_mock_object(class_, args.access)
    mock_implementation = _generate_mock_implementation(
        mock_implementation_name, class_, args.access)

    new_header = _generate_header(class_, mock_object, mock_implementation, args.input_path)
    new_source = _generate_source(class_, args.output_path)

    return new_header, new_source


def _generate_header(class_: types.Class,
                     mock_object: types.Class,
                     mock_implementation: types.Class,
                     input_path: str) -> str:
    result = ''

    result += _include_guard_open(class_.name)
    result += '\n'

    result += _include_angled_brackets(DRMOCK_INCLUDE_PATH + 'Mock.h')
    result += _include_quotes(os.path.abspath(input_path))
    result += '\n'

    # If explicit instantiations are allowed, declare them in the .h and
    # define them in the .cpp.
    if class_.explicit_instantiation_allowed():
        # Use set in order to discard duplicates (which occur if methods
        # have cv-qualified overloads with the same signature, for example).
        method_templates = {_generate_method_template(class_.full_name(), each)
                            for each in class_.get_virtual_methods()}
        result += '\n'.join(_explicit_instantiation_decl(each) for each in method_templates)
        result += '\n'

    result += str(mock_object)
    result += '\n'
    result += '\n'
    result += str(mock_implementation)
    result += '\n'
    result += '\n'
    result += _include_guard_close(class_.name)

    return result


def _generate_source(class_: types.Class, header_path: str) -> str:
    """

    Args:
        class_: ...
        header_path: Absolute path to the source's header path.
    """
    result = ''
    if class_.explicit_instantiation_allowed():
        # Use set in order to discard duplicates (which occur if methods
        # have cv-qualified overloads with the same signature, for example).
        method_templates = {_generate_method_template(class_.full_name(), each)
                            for each in class_.get_virtual_methods()}
        result += _include_quotes(header_path)
        result += '\n'
        result += '\n'.join(_explicit_instantiation_definition(each)
                            for each in method_templates)
    else:
        result = '// This source file is intentionally left blank'  # To prevent AutoGen warnings.
    return result


def _generate_mock_object(class_: types.Class, access: list[str]) -> types.Class:
    result = types.Class(_generate_mock_object_class_name(class_))
    result.enclosing_namespace = MOCK_OBJECT_ENCLOSING_NAMESPACE
    result.template = class_.template
    overloads = overload.get_overloads_of_class(class_, access)

    type_aliases = class_.get_type_aliases()
    for each in type_aliases:
        each.access = 'private'  # This is for aesthetic reasons!
    result.members += type_aliases

    result.members.append(Friend(class_.full_name(), 'private'))

    # NOTE State object must be default initialized _before_ the
    # shared_ptrs, so it must occur above them in the member list.
    state_object = types.Variable(
        overload.STATE_OBJECT_NAME, 'std::shared_ptr<StateObject>',
        ['std::make_shared<StateObject>()'], access='private')
    result.members.append(state_object)

    shared_ptrs = sum([each.generate_shared_ptrs() for each in overloads], [])
    result.members += shared_ptrs

    method_collection = types.Variable(
        name=METHOD_COLLECTION_NAME,
        type='MethodCollection',
        default_args=['{' + ', '.join(each.name for each in shared_ptrs) + '}'],
        access='private')
    result.members.append(method_collection)

    # NOTE It's important to add the dispatch methods _before_ the
    # getters; otherwise, you'll get the following compiler error:
    #
    # function 'f_dispatch' with # deduced return type cannot be used
    # before it is defined
    result.members += sum([each.generate_dispatch_methods() for each in overloads], [])

    verify_state1 = types.Method(
        name='verifyState',
        return_type='bool',
        params=['const std::string& state'],
        body=f'return {overload.STATE_OBJECT_NAME}->get() == state;')
    verify_state2 = types.Method(
        name='verifyState',
        return_type='bool',
        params=['const std::string& slot', 'const std::string& state'],
        body=f'return {overload.STATE_OBJECT_NAME}->get(slot) == state;')
    result.members.append(verify_state1)
    result.members.append(verify_state2)

    make_formatted_error_string = types.Method(
        name='makeFormattedErrorString',
        return_type='std::string',
        const=True,
        params=[],
        body='return methods.makeFormattedErrorString();')
    result.members.append(make_formatted_error_string)

    verify = types.Method(
        name='verify',
        return_type='bool',
        body=f'return {METHOD_COLLECTION_NAME}.verify();')
    result.members.append(verify)

    result.members += [each.generate_getter() for each in overloads]

    return result


def _generate_mock_implementation(name: str, class_: types.Class, access: list[str]) -> types.Class:
    result = types.Class(name)
    result.enclosing_namespace = class_.enclosing_namespace
    result.template = class_.template
    result.q_object = class_.q_object
    result.parent = class_.full_name()
    result.final = True

    result.members = class_.get_type_aliases()

    # Set the class as parent for all methods.
    overloads = overload.get_overloads_of_class(class_, access)
    default_ctor = types.Constructor(
        name=name,
        template=types.TemplateDecl([f'... {FORWARDING_CTOR_TEMPLATE_PARAMS}']),
        params=[f'{FORWARDING_CTOR_TEMPLATE_PARAMS}&&... ts'],
        initializer_list=[
            result.parent + '{' + f'std::forward<{FORWARDING_CTOR_TEMPLATE_PARAMS}>(ts)...' + '}'],
        body='\n'.join(sum([each.generate_set_parent() for each in overloads], []))
    )
    result.members.append(default_ctor)

    mock_implementation = types.Variable(
        name=overload.MOCK_OBJECT_NAME,
        type=_generate_mock_object_full_class_name(class_),
        mutable=True)
    result.members.append(mock_implementation)

    result.members += sum([each.generate_mock_implementations() for each in overloads], [])

    return result


def _include_quotes(file: str) -> str:
    return f'#include "{file}"\n'


def _include_angled_brackets(file: str) -> str:
    return f'#include <{file}>\n'


def _include_guard_macro(name: str) -> str:
    return INCLUDE_GUARD_PREFIX + name


def _include_guard_open(name: str) -> str:
    result = ''
    result += '#ifndef ' + _include_guard_macro(name) + '\n'
    result += '#define ' + _include_guard_macro(name) + '\n'
    return result


def _include_guard_close(name: str) -> str:
    return '#endif /* ' + _include_guard_macro(name) + ' */'


def _generate_method_template(parent: str, method: types.Method) -> str:
    """Return template for explicit instantiation of C++ Method object."""
    decayed_signature = [str(method.return_type)] \
        + [str(each.get_decayed()) for each in method.params]
    return METHOD_CPP_CLASS + '<' + parent + ', ' + ', '.join(decayed_signature) + '>'


def _explicit_instantiation_decl(expr: str) -> str:
    return 'extern template class ' + expr + ';'


def _explicit_instantiation_definition(expr: str) -> str:
    return 'template class ' + expr + ';'


@dataclasses.dataclass
class Friend:
    name: str
    access: str = 'public'

    def __str__(self):
        return f'friend class {self.name};'


def _generate_mock_object_class_name(class_: types.Class) -> str:
    return MOCK_OBJECT_PREFIX + class_.name


def _generate_mock_object_full_class_name(class_: types.Class):
    result = ''
    result += ''.join(each + '::' for each in MOCK_OBJECT_ENCLOSING_NAMESPACE)
    result += _generate_mock_object_class_name(class_)
    if class_.template:
        result += utils.template(class_.template.get_args())
    return result
