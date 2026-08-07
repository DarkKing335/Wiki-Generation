"""Unit tests for the Java AST parser (US-1.3).

Tests verify extraction of:
- Packages & imports
- Classes, interfaces, enums with modifiers
- Annotations with arguments
- Fields with types and visibility
- Methods with signatures, parameters, Javadoc, throws
- Constructors
- Inheritance (extends, implements)
- Relationships (call graph edges)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core_indexing.models import Language, SymbolKind
from core_indexing.parsers.java_parser import JavaParser
from tests.conftest import read_fixture, JAVA_FIXTURES_DIR


@pytest.fixture
def parser() -> JavaParser:
    return JavaParser()


@pytest.fixture
def user_service_index(parser: JavaParser):
    content = read_fixture(JAVA_FIXTURES_DIR / "UserService.java")
    return parser.parse(
        file_path=str(JAVA_FIXTURES_DIR / "UserService.java"),
        content=content,
        repo_path=str(JAVA_FIXTURES_DIR.parent.parent),
    )


@pytest.fixture
def order_controller_index(parser: JavaParser):
    content = read_fixture(JAVA_FIXTURES_DIR / "OrderController.java")
    return parser.parse(
        file_path=str(JAVA_FIXTURES_DIR / "OrderController.java"),
        content=content,
        repo_path=str(JAVA_FIXTURES_DIR.parent.parent),
    )


@pytest.fixture
def order_status_index(parser: JavaParser):
    content = read_fixture(JAVA_FIXTURES_DIR / "OrderStatus.java")
    return parser.parse(
        file_path=str(JAVA_FIXTURES_DIR / "OrderStatus.java"),
        content=content,
        repo_path=str(JAVA_FIXTURES_DIR.parent.parent),
    )


@pytest.fixture
def user_repo_index(parser: JavaParser):
    content = read_fixture(JAVA_FIXTURES_DIR / "UserRepository.java")
    return parser.parse(
        file_path=str(JAVA_FIXTURES_DIR / "UserRepository.java"),
        content=content,
        repo_path=str(JAVA_FIXTURES_DIR.parent.parent),
    )


# ======================================================================
# Package & imports
# ======================================================================


class TestPackageAndImports:
    def test_package_extracted(self, user_service_index):
        assert user_service_index.package_or_namespace == "com.example.auth"

    def test_language_is_java(self, user_service_index):
        assert user_service_index.language == Language.JAVA

    def test_imports_extracted(self, user_service_index):
        import_names = [i.name for i in user_service_index.imports]
        assert "com.example.model.User" in import_names
        assert "com.example.repository.UserRepository" in import_names

    def test_relative_path(self, user_service_index):
        assert "fixtures/java/UserService.java" in user_service_index.file_path


# ======================================================================
# Class extraction
# ======================================================================


class TestClassExtraction:
    def test_class_found(self, user_service_index):
        classes = [s for s in user_service_index.symbols if s.kind == SymbolKind.CLASS]
        assert len(classes) >= 1
        class_names = [c.name for c in classes]
        assert "UserService" in class_names

    def test_class_fqn(self, user_service_index):
        cls = next(s for s in user_service_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "UserService")
        assert cls.fully_qualified_name == "com.example.auth.UserService"

    def test_class_modifiers(self, user_service_index):
        cls = next(s for s in user_service_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "UserService")
        assert "public" in cls.modifiers

    def test_class_annotations(self, user_service_index):
        cls = next(s for s in user_service_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "UserService")
        ann_names = [a.name for a in cls.annotations]
        assert "Service" in ann_names
        assert "Transactional" in ann_names

    def test_annotation_arguments(self, user_service_index):
        cls = next(s for s in user_service_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "UserService")
        trans = next(a for a in cls.annotations if a.name == "Transactional")
        assert trans.arguments.get("readOnly") == "false"

    def test_class_implements(self, user_service_index):
        cls = next(s for s in user_service_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "UserService")
        # Should detect implements interfaces
        assert len(cls.implements) >= 1

    def test_class_has_docstring(self, user_service_index):
        cls = next(s for s in user_service_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "UserService")
        assert cls.docstring is not None
        assert "authentication" in cls.docstring.lower()

    def test_class_line_range(self, user_service_index):
        cls = next(s for s in user_service_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "UserService")
        assert cls.range.start_line > 0
        assert cls.range.end_line >= cls.range.start_line


# ======================================================================
# Interface extraction
# ======================================================================


class TestInterfaceExtraction:
    def test_interface_found(self, user_repo_index):
        interfaces = [s for s in user_repo_index.symbols if s.kind == SymbolKind.INTERFACE]
        assert len(interfaces) >= 1
        assert any(i.name == "UserRepository" for i in interfaces)

    def test_interface_fqn(self, user_repo_index):
        iface = next(s for s in user_repo_index.symbols
                     if s.kind == SymbolKind.INTERFACE and s.name == "UserRepository")
        assert iface.fully_qualified_name == "com.example.repository.UserRepository"

    def test_interface_methods(self, user_repo_index):
        methods = [s for s in user_repo_index.symbols if s.kind == SymbolKind.METHOD]
        method_names = [m.name for m in methods]
        assert any("findByUsername" in n for n in method_names)
        assert any("findByEmail" in n for n in method_names)


# ======================================================================
# Enum extraction
# ======================================================================


class TestEnumExtraction:
    def test_enum_found(self, order_status_index):
        enums = [s for s in order_status_index.symbols if s.kind == SymbolKind.ENUM]
        assert len(enums) >= 1
        assert any(e.name == "OrderStatus" for e in enums)

    def test_enum_has_method(self, order_status_index):
        methods = [s for s in order_status_index.symbols if s.kind == SymbolKind.METHOD]
        assert any("isTerminal" in m.name for m in methods)


# ======================================================================
# Method extraction
# ======================================================================


class TestMethodExtraction:
    def test_methods_found(self, user_service_index):
        methods = [s for s in user_service_index.symbols if s.kind == SymbolKind.METHOD]
        method_names = [m.name for m in methods]
        assert any("authenticate" in n for n in method_names)
        assert any("registerUser" in n for n in method_names)

    def test_method_signature(self, user_service_index):
        auth = next(s for s in user_service_index.symbols
                    if s.kind == SymbolKind.METHOD and "authenticate" in s.name)
        assert auth.signature is not None
        assert auth.signature.return_type == "String"
        assert len(auth.signature.parameters) == 2
        param_names = [p.name for p in auth.signature.parameters]
        assert "username" in param_names
        assert "password" in param_names

    def test_method_throws(self, user_service_index):
        auth = next(s for s in user_service_index.symbols
                    if s.kind == SymbolKind.METHOD and "authenticate" in s.name)
        assert "AuthenticationException" in auth.signature.thrown_exceptions

    def test_method_javadoc(self, user_service_index):
        auth = next(s for s in user_service_index.symbols
                    if s.kind == SymbolKind.METHOD and "authenticate" in s.name)
        assert auth.docstring is not None
        assert "JWT token" in auth.docstring

    def test_method_annotations(self, user_service_index):
        auth = next(s for s in user_service_index.symbols
                    if s.kind == SymbolKind.METHOD and "authenticate" in s.name)
        ann_names = [a.name for a in auth.annotations]
        assert "Transactional" in ann_names

    def test_method_parent(self, user_service_index):
        auth = next(s for s in user_service_index.symbols
                    if s.kind == SymbolKind.METHOD and "authenticate" in s.name)
        assert auth.parent_symbol_id == "com.example.auth.UserService"

    def test_private_method(self, user_service_index):
        gen = next(s for s in user_service_index.symbols
                   if s.kind == SymbolKind.METHOD and "generateToken" in s.name)
        assert "private" in gen.modifiers


# ======================================================================
# Constructor extraction
# ======================================================================


class TestConstructorExtraction:
    def test_constructor_found(self, user_service_index):
        ctors = [s for s in user_service_index.symbols if s.kind == SymbolKind.CONSTRUCTOR]
        assert len(ctors) >= 1

    def test_constructor_parameters(self, user_service_index):
        ctor = next(s for s in user_service_index.symbols if s.kind == SymbolKind.CONSTRUCTOR)
        assert ctor.signature is not None
        assert len(ctor.signature.parameters) == 2


# ======================================================================
# Field extraction
# ======================================================================


class TestFieldExtraction:
    def test_fields_found(self, user_service_index):
        fields = [s for s in user_service_index.symbols if s.kind == SymbolKind.FIELD]
        assert len(fields) >= 2

    def test_field_types(self, user_service_index):
        fields = [s for s in user_service_index.symbols if s.kind == SymbolKind.FIELD]
        field_names = [f.name for f in fields]
        assert any("userRepository" in n for n in field_names)
        assert any("passwordEncoder" in n for n in field_names)

    def test_field_modifiers(self, user_service_index):
        fields = [s for s in user_service_index.symbols if s.kind == SymbolKind.FIELD]
        repo_field = next(f for f in fields if "userRepository" in f.name)
        assert "private" in repo_field.modifiers
        assert "final" in repo_field.modifiers

    def test_static_field(self, user_service_index):
        fields = [s for s in user_service_index.symbols if s.kind == SymbolKind.FIELD]
        default_role = next(f for f in fields if "DEFAULT_ROLE" in f.name)
        assert "static" in default_role.modifiers
        assert "final" in default_role.modifiers


# ======================================================================
# Controller (annotation-heavy)
# ======================================================================


class TestControllerExtraction:
    def test_controller_class_annotations(self, order_controller_index):
        cls = next(s for s in order_controller_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "OrderController")
        ann_names = [a.name for a in cls.annotations]
        assert "RestController" in ann_names
        assert "RequestMapping" in ann_names

    def test_request_mapping_argument(self, order_controller_index):
        cls = next(s for s in order_controller_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "OrderController")
        rm = next(a for a in cls.annotations if a.name == "RequestMapping")
        assert "/api/orders" in rm.arguments.get("value", "")

    def test_controller_methods(self, order_controller_index):
        methods = [s for s in order_controller_index.symbols if s.kind == SymbolKind.METHOD]
        method_names = [m.name for m in methods]
        assert any("getOrder" in n for n in method_names)
        assert any("createOrder" in n for n in method_names)
        assert any("listOrders" in n for n in method_names)

    def test_method_annotation(self, order_controller_index):
        get_order = next(s for s in order_controller_index.symbols
                         if s.kind == SymbolKind.METHOD and "getOrder" in s.name)
        ann_names = [a.name for a in get_order.annotations]
        assert "GetMapping" in ann_names
