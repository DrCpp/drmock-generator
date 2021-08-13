# SPDX-FileCopyrightText: 2021 Malte Kliemann, Ole Kliemann
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Classes for C++ AST node infos.

Most classes represent a type of AST node and feature a ``from_node``
``classmethod`` which may be created from an appropriate
``translator.Node`` object:

```python
@classmethod
def from_node(cls: _T, node: translator.Node) -> _T:
    ...
```

The ``node`` parameter **must** have the correct cursor kind, otherwise
the call will fail with an error.
"""

from __future__ import annotations

import copy
import collections
import dataclasses
from typing import Any, Optional, Sequence, Union
import clang.cindex

from drmock import utils

"""We're using an ``OrderedDict`` to ensure that in ``Method.mangled_name``
for example ``<=>`` is replaced _before_ ``<=`` to ensure that
``operator<=>`` becomes ``operatorSpaceship`` instead of
``operatorLesserOrEqualGreater``.
"""
_OPERATOR_SYMBOLS = collections.OrderedDict(
    [
        ("<=>", "SpaceShip"),
        ("->*", "PointerToMember"),
        ("co_await", "CoAwait"),
        ("==", "Equal"),
        ("!=", "NotEqual"),
        ("<=", "LesserOrEqual"),
        (">=", "GreaterOrEqual"),
        ("<<", "StreamLeft"),
        (">>", "StreamRight"),
        ("&&", "And"),
        ("||", "Or"),
        ("++", "Increment"),
        ("--", "Decrement"),
        ("->", "Arrow"),
        ("()", "Call"),
        ("[]", "Brackets"),
        ("+", "Plus"),
        ("-", "Minus"),
        ("*", "Ast"),
        ("/", "Div"),
        ("%", "Modulo"),
        ("^", "Caret"),
        ("&", "Amp"),
        ("|", "Pipe"),
        ("~", "Tilde"),
        ("!", "Not"),
        ("=", "Assign"),
        ("<", "Lesser"),
        (">", "Greater"),
        (",", "Comma"),
    ]
)


def from_node(node: translator.Node) -> Any:
    """Create an instance of an appropriate class of this module from a
    node.

    Args:
        The node to the create the object from

    The type of the instance is determined from the node's ``kind``
    property.

    Raises:
        ValueError: If the appropriate class cannot be determined
    """
    if not hasattr(from_node, "_DISPATCH"):
        from_node._DISPATCH = {
            clang.cindex.CursorKind.PARM_DECL: Type,
            clang.cindex.CursorKind.CXX_METHOD: Method,
            clang.cindex.CursorKind.TYPE_ALIAS_TEMPLATE_DECL: TypeAlias,
            clang.cindex.CursorKind.TYPE_ALIAS_DECL: TypeAlias,
        }
    cursor = node.cursor
    type_ = from_node._DISPATCH.get(cursor.kind, None)
    if not type_:
        keys = ", ".join(each.cursor.kind.name for each in from_node._DISPATCH)
        raise ValueError(
            f"Invalid CursorKind. Expected: {keys}; received: {cursor.kind.name}"
        )
    return type_.from_node(node)


@dataclasses.dataclass
class Type:
    """For C++ type declarations.

    Types are stored in "layers", where each layer represents an
    indirection due to cv qualifiers, references or pointers. Each layer
    points to the next layer using the ``inner`` attribute. The
    inner-most layer is a string which holds the spelling of the core
    type (for example, the inner-most type for  ``const
    std::vector<int>&`` is ``'std::vector<int>'``).

    Due to the nature of this design, artificial _naked_ layers which
    hold no information are possible. For example:

    >>> type_ = Type('int')
    >>> naked = Type(type_)  # Represents same type, but with naked first layer
    """

    inner: Union[str, Type]
    const: bool = False
    volatile: bool = False
    lvalue_ref: bool = False
    rvalue_ref: bool = False
    pointer: bool = False
    parameter_pack: bool = False

    def get_decayed(self) -> Type:
        """Return the decayed version of ``self``."""
        # Note that if an instance of `Type` is a reference, then its
        # const qualifier is saved in the inner type. This is due to the
        # confusion between the terms "const reference" and "reference
        # to const": The distinction between "const reference" and
        # "reference to const" is unnecessary, and the former is only a
        # shorthand for the latter. The same goes for volatile
        # qualifiers. Therefore, when decaying a reference, the cv
        # qualifiers must be removed from the inner type; otherwise,
        # they must be removed from the instance itself.

        result = self._get_simplified()  # In case top item is naked.
        if result.lvalue_ref or result.rvalue_ref:
            result.lvalue_ref = False
            result.rvalue_ref = False
            if not isinstance(result.inner, str):
                result.inner.const = False
                result.inner.volatile = False
        else:
            result.const = False
            result.volatile = False
        result = (
            result._get_simplified()
        )  # If ``result`` was a reference, it's now naked.
        return result

    def _get_simplified(self, first_pass: bool = True) -> Type:
        """Return equivalent type with naked layers removed.

        Args:
            first_pass:
                Optional argument for recursing, **must** not be set by
                the caller
        """
        # Find outer-most non-naked position in the hierarchy. This type
        # will form the outer Type object of the result.
        result = self
        while not isinstance(result.inner, str) and result._is_naked():
            result = result.inner

        # Create a copy of the new base object on the first iteration.
        # On later iterations, we need to make sure that
        if first_pass:
            result = copy.deepcopy(result)

        # If the outer type is a base-type, we're done. On a later
        # iteration, the last type may be naked and must be skipped. On
        # the first iteration, the last naked type is used as wrapper.
        if isinstance(result.inner, str):
            if not first_pass and result._is_naked():
                return result.inner
            return result

        # Otherwise, simplify the inner type.
        result.inner = result.inner._get_simplified(False)
        return result

    def _is_naked(self) -> bool:
        """Check if ``self`` is naked."""
        return (
            not self.const
            and not self.volatile
            and not self.lvalue_ref
            and not self.rvalue_ref
            and not self.pointer
            and not self.parameter_pack
        )

    def __str__(self):
        result = str(self.inner)
        result += self.lvalue_ref * " &" + self.rvalue_ref * " &&"
        if self.pointer:
            result += " *" + self.const * " const" + self.volatile * " volatile"
        else:
            result = self.const * "const " + self.volatile * "volatile " + result
        result += self.parameter_pack * " ..."
        return result

    @classmethod
    def from_node(cls, node: translator.Node) -> Type:
        # NOTE The following is a hack to solve some rather unfortunate
        # behavior of python clang. When using a type alias such as
        #
        # namespace outer { namespace inner {
        #
        # class Foo
        # {
        # public:
        #   using T = std::shared_ptr<int>;
        # }
        #
        # } // namespace outer::inner
        #
        # in a function declaration,
        #
        # void f(T);
        #
        # ``T`` is expanded into ``inner::outer::Foo``, unless ``T`` is
        # suffciently buried (for instance, ``std::shared_ptr<T>`` will
        # not be expanded). This seems to happen with ``spelling``,
        # ``type.spelling``, ``displayname``, etc.
        #
        # Leaving this unchanged would render the ``Method`` object
        # corresponding to this declaration dependent on the class that
        # the declaration occured in. But we want to move the method (or
        # the type alias) into another class!
        #
        # Another matter is that, even if ``Foo`` is a class template, the
        # expanded name will not contain the template parameters
        # (``outer::inner::Foo`` instead of ``outer::inner::Foo<...>``).
        # Therefore, parsing and printing a class template with type
        # aliases will result in code that will raise a compiler error.
        #
        # The problem is solved by taking the tokens of the parameter
        # declarations and joining them into a string.
        #
        # But two related problems arise when using tokens. If a
        # variable name is given to a parameter, as in
        #
        # f(const T & ... foo);
        #                 ^^^
        #
        # then that name will appear in the tokens. It must therefore be
        # removed from the tokens. But beware! If no variable name or
        # '...' is present in the parameter declaration, then an outer
        # ``const`` as in
        #
        # f(const T* const);
        #            ^^^^^
        #
        # is lost when considering the cursor's tokens, and thus
        # ``from_tokens`` cannot be used. Fortunately, this outer const
        # qualifier can be recognized using clang python. Thus, in the
        # case of a parameter pack or a parameter decl with variable
        # name, ``from_tokens`` may be called after popping the variable
        # name. Otherwise, a complex route must be taken.

        # Check for variable name or parameter pack and call ``from_tokens``.
        tokens = node.get_tokens()  # ['const', 'T', '&', '...', 'foo']
        var = node.cursor.spelling  # 'foo'
        if var != "" and tokens[-1] == var:  # Remove variable/parameter name.
            tokens.pop()
        result = cls.from_tokens(tokens)
        # In some cases (e.g. ``const T*const``), the outer const is not
        # found in the tokens, so we must use class methods.
        result.const = node.cursor.type.is_const_qualified()
        result.volatile = node.cursor.type.is_volatile_qualified()
        return result

    @classmethod
    def from_tokens(cls, tokens: Sequence[str]) -> Type:
        """Create a ``Type`` instance from a sequence of tokens."""
        t = cls("T")  # Use temporary inner name to init ``t``.

        # Read from the right.
        while True:
            if tokens[-1] == "const":
                t.const = True
                tokens.pop()
            elif tokens[-1] == "volatile":
                t.volatile = True
                tokens.pop()
            elif tokens[-1] == "...":
                t.parameter_pack = True
                tokens.pop()
            elif tokens[-1] == "*":
                t.pointer = True
                tokens.pop()
                break
            elif tokens[-1] == "&":
                t.lvalue_ref = True
                tokens.pop()
                break
            elif tokens[-1] == "&&":
                t.rvalue_ref = True
                tokens.pop()
                break
            else:
                break

        # If ``t`` is a pointer or a reference, reassemble the remaining
        # tokens and call ``from_tokens`` recursively.
        if t.pointer or t.lvalue_ref or t.rvalue_ref:
            t.inner = Type.from_tokens(tokens)
            return t._get_simplified()

        # If ``t`` is not a pointer or a reference, then read from the
        # left.
        while True:
            if tokens[0] == "const":
                t.const = True
                tokens.pop(0)
            elif tokens[0] == "volatile":
                t.volatile = True
                tokens.pop(0)
            else:
                break

        # Terminate the recursion by reassembeling the remaining tokens.
        t.inner = " ".join(tokens)
        return t._get_simplified()

    @classmethod
    def from_spelling(cls, spelling: str) -> Type:
        """Create a ``Type`` instance from a cursor spelling."""
        tokens = spelling.split(" ")
        return cls.from_tokens(tokens)


class TemplateDecl:  # For TemplateDeclaration
    """For template declarations."""

    def __init__(self, params: Sequence[str]):
        """Args:
            params: A list of the template decl's params

        The ``class``/``typename`` keyword **must** be omitted. Variadic
        template parameters are specified using a prefixed ``'... '``.
        For example:

        >>> decl = TemplateDecl(['T', '... Ts'])
        """
        self._params = params

    def get_args(self) -> list[str]:
        """Get the decl's args.

        Note that the tokens of a variadic template param are swapped.
        For example:

        >>> decl = TemplateDecl(['T', '... Ts'])
        >>> decl.get_args()
        ['T', 'Ts ...']
        """
        return [
            utils.swap(r"\.\.\. (.*)", r"\1 ...", each)
            if each.startswith("...")
            else each
            for each in self._params
        ]

    def __eq__(self, other):
        if not isinstance(other, TemplateDecl):
            return NotImplemented
        return self._params == other._params

    def __str__(self):
        result = ""
        result += "template<"
        result += ", ".join(f"typename {each}" for each in self._params)
        result += ">"
        return result

    @classmethod
    def from_node(cls, node: translator.Node) -> TemplateDecl:
        params = []
        for each in node.get_children():
            if each.cursor.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
                # The following is a hack used to circumvent the problem
                # that `cindex.CursorKind.TEMPLATE_TYPE_PARAMETER` is
                # unable to recognize variadic template parameters.
                # Fortunately, it is possible to detect "..." using the
                # `get_tokens()` method.
                tokens = (
                    each.get_tokens()
                )  # ["typename", "T"] or ["typename", "...", "Ts"]
                name = " ".join(tokens[1:])  # "T" or "... Ts"
                params.append(name)
        result = TemplateDecl(params)
        return result


class Constructor:
    """For C++ class constructors."""

    def __init__(
        self,
        name: str,
        params: Optional[Sequence[Union[str, Type]]] = None,
        template: Optional[TemplateDecl] = None,
        initializer_list: Optional[Sequence[str]] = None,
        body: str = "",
        access: str = "public",
    ):
        """Args:
        name: The ctor's name
        params: The params
        template: A template decl if the ctor is templated
        initializer_list: The entries of the ctor's initializer list
        body: The body
        access: The access specifier of the object
        """
        self._name = name
        if params is not None:
            self._params = params
        else:
            self._params = []
        self._template = template
        if initializer_list is not None:
            self._initializer_list = initializer_list
        else:
            self._initializer_list = []
        self._body = body
        self._access = access

    @property
    def access(self) -> str:
        """The access specifier of the object."""
        return self._access

    def __str__(self) -> str:
        result = ""
        if self._template:
            result += str(self._template) + "\n"
        result += self._name
        params = ", ".join(str(each) for each in self._params)
        result += f"({params})"
        if self._initializer_list:
            result += " : " + ", ".join(self._initializer_list)
        result += "\n{\n"
        result += utils.indent(self._body)
        result += "\n}"
        return result


@dataclasses.dataclass
class Method:
    """For C++ class methods.

    Attributes:
        name: The method's name
        params: The method's parameters
        return_type: The method's return type
        template: The method's template declaration (if available)
        const: Indicates if the method is const-qualified
        volatile: Indicates if the method is volatile-qualified
        lvalue: Indicates if the method is lvalue qualified
        rvalue: Indicates if the method is rvalue qualified
        virtual: Indicates if the method is virtual
        pure_virtual: Indicates if the method is pure virtual
        override: Indicates if the method has the ``override`` specifier
        noexcept: Indicates if the method has the ``noexcept`` specifier
        operator: Indicates if the method is an operator
        body: The method's body (if available)
        access: The method's access specifier

    Beware! By manually setting these attributes, you **may** impossible
    configurations, methods which are pure virtual but not virtual, for
    example.

    Each method has a _mangled name_. If the method is an operator, the
    operator symbol is replaced with an alphanumeric string which
    describes that symbol (see ``_OPERATOR_SYMBOLS``), otherwise, the
    mangled name is the method's normal name.
    """

    name: str
    params: Sequence[Union[str, Type]] = dataclasses.field(default_factory=list)
    return_type: Type = Type("void")
    template: Optional[TemplateDecl] = None
    const: bool = False
    volatile: bool = False
    lvalue: bool = False
    rvalue: bool = False
    virtual: bool = False
    pure_virtual: bool = False
    override: bool = False
    noexcept: bool = False
    operator: bool = False
    body: Optional[str] = None
    access: str = "public"

    def mangled_name(self) -> str:
        """Return the mangled name of the method."""
        result = self.name
        for k, v in _OPERATOR_SYMBOLS.items():
            result = result.replace(k, v)
        return result

    def __str__(self) -> str:
        result = ""
        if self.template:
            result += str(self.template) + "\n"
        if self.virtual:
            result += "virtual "
        if (
            self.return_type
        ):  # This check makes sure that no ugly indentation occurs for ctors!
            result += str(self.return_type) + " "
        result += self.name
        params = ", ".join(str(each) for each in self.params)
        result += f"({params})"
        result += self.const * " const"
        result += self.volatile * " volatile"
        result += self.lvalue * "&"
        result += self.rvalue * "&&"
        result += self.noexcept * " noexcept"
        result += self.override * " override"  # This must always be last!
        if self.body:
            result += "\n{\n"
            result += utils.indent(self.body)
            result += "\n}"
        else:
            if self.pure_virtual:
                result += " = 0"
            result += ";"
        return result

    @classmethod
    def from_node(cls, node: translator.Node) -> Method:
        # NOTE The following is a hack to solve some rather unfortunate
        # behavior of python clang. When using a type alias such as
        #
        # namespace outer { namespace inner {
        #
        # class Foo
        # {
        # public:
        #   using T = std::shared_ptr<int>;
        # }
        #
        # } // namespace outer::inner
        #
        # in a function declaration,
        #
        # void f(T);
        #
        # ``T`` is expanded into ``inner::outer::Foo``, unless ``T`` is
        # suffciently buried (for instance, ``std::shared_ptr<T>`` will
        # not be expanded). This seems to happen with ``spelling``,
        # ``type.spelling``, ``displayname``, etc.
        #
        # Leaving this unchanged would render the ``Method`` object
        # corresponding to this declaration dependent on the class that
        # the declaration occured in. But we want to move the method (or
        # the type alias) into another class!
        #
        # Another matter is that, even if ``Foo`` is a class template, the
        # expanded name will not contain the template parameters
        # (``outer::inner::Foo`` instead of ``outer::inner::Foo<...>``).
        # Therefore, parsing and printing a class template with type
        # aliases will result in code that will raise a compiler error.
        #
        # ``Method.from_node()`` uses ``cindex.Type.get_canonical()`` to
        # assemble the return type. If ``Foo`` is a class template and a
        # template parameter of ``Foo`` appears as parameter in the type
        # alias, it is represented in the form
        #
        # shared_ptr<type-parameter-0-i>
        #
        # where ``i`` is the index of the parameter (note the missing
        # ``std::``).
        #
        # The current solution is to gather the tokens of the CXX_METHOD
        # cursor between the virtual keyword and the function name, and
        # pass these to ``Type.from_tokens``.
        #
        # virtual const T * const f() = 0;
        #         ^^^^^^^^^^^^^^^
        #
        # Special care must be taken when dealing with operators.

        f = Method(node.cursor.spelling)
        f.params = [
            from_node(each)
            for each in node.get_children()
            if each.cursor.kind == clang.cindex.CursorKind.PARM_DECL
        ]
        tokens = node.get_tokens()
        if tokens[0] == "virtual":
            tokens.pop(0)

        # Check if the name of ``f`` occurs in the tokens. If not, then
        # ``f`` is an operator.
        if f.name not in tokens:
            delim = tokens.index("operator")
        else:
            delim = tokens.index(f.name)
        f.return_type = Type.from_tokens(tokens[:delim])

        # The following is a hack to obtain the volatile qualifier and
        # override keywords:
        #
        # void f(...) const volatile noexcept = 0;
        #             ^^^^^^^^^^^^^^^^^^^^^^^
        #
        # Get these tokens! (There is, apparently, no other way to check
        # for cv qualifiers using python clang.)
        delim = max(
            index for index, value in enumerate(tokens) if value == ")"
        )  # Index of last closing parens.
        keywords = tokens[delim + 1 :]
        if "override" in keywords:
            f.override = True
        if "volatile" in keywords:
            f.volatile = True
        if "&" in keywords:
            f.lvalue = True
        if "&&" in keywords:
            f.rvalue = True

        # Const qualifiers, virtual keywords, and exception
        # specifications can be obtained using python clang.
        f.const = node.cursor.is_const_method()
        f.virtual = node.cursor.is_virtual_method()
        f.pure_virtual = node.cursor.is_pure_virtual_method()
        if (
            node.cursor.exception_specification_kind
            == clang.cindex.ExceptionSpecificationKind.BASIC_NOEXCEPT
        ):  # noqa: E501
            f.noexcept = True

        # ``f`` is an operator, if its name matches the following regex.
        if f.name.replace("operator", "") in _OPERATOR_SYMBOLS:
            f.operator = True
        return f


@dataclasses.dataclass
class TypeAlias:
    """For C++ (template and non-template) type aliases.

    Attributes:
        name: The alias
        typedef: The aliased type
        template: The type alias' template decl (if available)

    Example:
        >>> TypeAlias('Vector', 'std::vector<T>', TemplateDecl(['T']))
        # template<typename T> using Vector<T> = std::vector<T>;
    """

    name: str
    typedef: str
    template: Optional[TemplateDecl] = None

    def __str__(self):
        result = ""
        if self.template:
            result += str(self.template) + " "
        result += f"using {self.name} = {str(self.typedef)};"
        return result

    @classmethod
    def from_node(cls, node: translator.Node) -> TypeAlias:
        if node.cursor.kind == clang.cindex.CursorKind.TYPE_ALIAS_TEMPLATE_DECL:
            template = TemplateDecl.from_node(node)
            node = next(
                each
                for each in node.get_children()
                if each.cursor.kind == clang.cindex.CursorKind.TYPE_ALIAS_DECL
            )
        else:
            template = None
        result = TypeAlias(
            node.cursor.spelling, node.cursor.underlying_typedef_type.spelling
        )
        result.template = template
        return result


@dataclasses.dataclass
class Class:
    """For C++ classes.

    Attributes:
        name: The class name
        enclosing_namespace: The namespace the class is contained in
        members: A list of the class' members (see note below)
        final: Indicates if the class is final
        q_object: Indicates if the class is a ``Q_OBJECT``
        parent: The name of the class' parent (if available)
        template: The template decl (if available)

    Note that this class is not a faithful representation of C++
    classes. For example, the order of members may change during
    loading. Also, we don't check for base classes, etc.
    """

    name: str
    enclosing_namespace: list[str] = dataclasses.field(default_factory=list)
    members: list[Union[Constructor, Method, Variable]] = dataclasses.field(
        default_factory=list
    )  # Methods, variables, type aliases!
    final: bool = False
    q_object: bool = False
    # We're assuming at most one (public) base class! NOTE This does not mean
    # that the mockee cannot inherit from more than one parent. We only use
    # the ``parent`` field for later printing the mock class.
    parent: Optional[str] = None
    template: Optional[TemplateDecl] = None

    def full_name(self) -> str:
        """Return the fully qualified class name."""
        result = ""
        result += "".join(each + "::" for each in self.enclosing_namespace)
        result += self.name
        if self.template:
            result += utils.template(self.template.get_args())
        return result

    def get_virtual_methods(self) -> list[Method]:
        return [
            each for each in self.members if isinstance(each, Method) and each.virtual
        ]

    def get_type_aliases(self) -> list[TypeAlias]:
        return [each for each in self.members if isinstance(each, TypeAlias)]

    def explicit_instantiation_allowed(self) -> bool:
        """Check if explicit instantiations of the class' method are
        possible.

        As of C++17, this means that the class is not a class template
        nor contains type aliases.
        """
        return (self.template is None) and not self.get_type_aliases()

    def __str__(self):
        result = ""

        if self.enclosing_namespace:
            result += " ".join(
                "namespace " + each + " {" for each in self.enclosing_namespace
            )
            result += "\n"
            result += "\n"

        if self.template:
            result += str(self.template) + "\n"

        result += "class " + self.name + self.final * " final"
        if self.parent:  # If self is derived (as C++ class).
            result += " : public " + self.parent

        result += "\n"  # End class decl line.
        result += "{\n"

        result += self.q_object * "  Q_OBJECT\n\n"

        access = "private"
        for each in self.members:
            # Observe access specifier change.
            if access != each.access:
                access = each.access
                result += "\n"
                result += each.access + ":\n"

            result += utils.indent(str(each))
            result += "\n"

        result += "};"

        if self.enclosing_namespace:
            result += "\n\n"
            namespace_count = len(self.enclosing_namespace)
            result += (
                namespace_count * "}"
                + " // namespace "
                + "::".join(self.enclosing_namespace)
            )

        return result

    @classmethod
    def from_node(cls, node: translator.Node) -> Class:
        """Create ``Class`` object from node.

        Args:
            node: The node to create the object from

        Returns:
            The newly created ``Class`` object

        Note that the ``enclosing_namespace`` field of the ``Class``
        object will *not* be set, as they cannot be read from the class
        node. This is done by the
        ``translator.Node.find_matching_class`` method.

        Note that ``from_node`` will only transcribe information
        relevant to our mocking process and therefore not faithfully
        represent the underlying C++ class. For example, ctor, dtors,
        field variables, etc. will *not* be transcribed into the
        ``Class`` object.
        """
        assert node.cursor.kind in {
            clang.cindex.CursorKind.CLASS_DECL,
            clang.cindex.CursorKind.CLASS_TEMPLATE,
        }
        result = cls("T")  # Use temporary class name for init.
        result.name = node.cursor.spelling
        if node.cursor.kind == clang.cindex.CursorKind.CLASS_TEMPLATE:
            result.template = TemplateDecl.from_node(node)

        access = "private"
        for each in node.get_children():
            IGNORED_CURSORS = {
                clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER,
                clang.cindex.CursorKind.DESTRUCTOR,
                clang.cindex.CursorKind.CXX_BASE_SPECIFIER,
                clang.cindex.CursorKind.USING_DIRECTIVE,
            }
            if each.cursor.kind in IGNORED_CURSORS:
                continue

            # A field decl can mean one of two things: (1) A field in a
            # non-abstract base class, (2) a macro notification created
            # by us.
            if each.cursor.kind == clang.cindex.CursorKind.FIELD_DECL:
                tokens = each.get_tokens()  # ['int', 'Q_OBJECT'], etc.
                assert tokens
                tokens.pop(0)  # ['Q_OBJECT']
                var = tokens.pop() if tokens else None
                if var == "Q_OBJECT":
                    result.q_object = True
                    continue

            if each.cursor.kind == clang.cindex.CursorKind.CXX_ACCESS_SPEC_DECL:
                access = _access_spec_decl_from_node(each)

            MEMBER_TYPES = {
                clang.cindex.CursorKind.CXX_METHOD,
                clang.cindex.CursorKind.TYPE_ALIAS_TEMPLATE_DECL,
                clang.cindex.CursorKind.TYPE_ALIAS_DECL,
            }
            if each.cursor.kind in MEMBER_TYPES:
                member = from_node(each)
                member.access = access
                result.members.append(member)

        return result


@dataclasses.dataclass
class Variable:
    """For C++ member variable declarations.

    Attributes:
        name: The variable name
        type: The type declaration
        default_args: The default value of the member
        mutable: Indicates if the member is mutable
        access: The member's access specifier
    """

    name: str
    type: Type
    default_args: Sequence[str] = dataclasses.field(default_factory=list)
    mutable: bool = False
    access: str = "public"

    def __str__(self):
        result = ""
        result += self.mutable * "mutable "
        result += str(self.type) + " "
        result += self.name
        result += "{" + ", ".join(self.default_args) + "}"
        result += ";"
        return result


def _access_spec_decl_from_node(node: translator.Node) -> str:
    """Get access specifier token from ``ACCESS_SPEC_DECL``."""
    tokens = node.get_tokens()  # public, protected, private (slots)
    # Since `slots` and `signals` is #defined as empty, an empty access
    # spec decl is most likely ``signals:``.
    if not tokens:
        return "signals"
    return tokens[0]
