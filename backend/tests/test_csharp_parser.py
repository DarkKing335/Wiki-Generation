"""Unit tests for the C# AST parser (US-1.4).

Tests verify extraction of:
- Namespaces & using directives
- Classes, interfaces, enums, structs with modifiers
- Attributes with arguments
- Properties with accessor info ({ get; set; })
- Fields with types and visibility
- Methods with async status, parameters, XML doc comments
- Constructors
- Inheritance / implementation relationships
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core_indexing.models import Language, SymbolKind
from core_indexing.parsers.csharp_parser import CSharpParser
from tests.conftest import read_fixture, CSHARP_FIXTURES_DIR


@pytest.fixture
def parser() -> CSharpParser:
    return CSharpParser()


@pytest.fixture
def order_controller_index(parser: CSharpParser):
    content = read_fixture(CSHARP_FIXTURES_DIR / "OrderController.cs")
    return parser.parse(
        file_path=str(CSHARP_FIXTURES_DIR / "OrderController.cs"),
        content=content,
        repo_path=str(CSHARP_FIXTURES_DIR.parent.parent),
    )


@pytest.fixture
def order_service_index(parser: CSharpParser):
    content = read_fixture(CSHARP_FIXTURES_DIR / "OrderService.cs")
    return parser.parse(
        file_path=str(CSHARP_FIXTURES_DIR / "OrderService.cs"),
        content=content,
        repo_path=str(CSHARP_FIXTURES_DIR.parent.parent),
    )


@pytest.fixture
def order_status_index(parser: CSharpParser):
    content = read_fixture(CSHARP_FIXTURES_DIR / "OrderStatus.cs")
    return parser.parse(
        file_path=str(CSHARP_FIXTURES_DIR / "OrderStatus.cs"),
        content=content,
        repo_path=str(CSHARP_FIXTURES_DIR.parent.parent),
    )


@pytest.fixture
def iorder_service_index(parser: CSharpParser):
    content = read_fixture(CSHARP_FIXTURES_DIR / "IOrderService.cs")
    return parser.parse(
        file_path=str(CSHARP_FIXTURES_DIR / "IOrderService.cs"),
        content=content,
        repo_path=str(CSHARP_FIXTURES_DIR.parent.parent),
    )


# ======================================================================
# Namespace & usings
# ======================================================================


class TestNamespaceAndUsings:
    def test_namespace_extracted(self, order_controller_index):
        assert order_controller_index.package_or_namespace == "MyApp.Controllers"

    def test_language_is_csharp(self, order_controller_index):
        assert order_controller_index.language == Language.CSHARP

    def test_usings_extracted(self, order_controller_index):
        import_names = [i.name for i in order_controller_index.imports]
        assert "System" in import_names
        assert "Microsoft.AspNetCore.Mvc" in import_names
        assert "MyApp.Services" in import_names

    def test_relative_path(self, order_controller_index):
        assert "fixtures/csharp/OrderController.cs" in order_controller_index.file_path


# ======================================================================
# Class extraction
# ======================================================================


class TestClassExtraction:
    def test_class_found(self, order_controller_index):
        classes = [s for s in order_controller_index.symbols if s.kind == SymbolKind.CLASS]
        assert len(classes) >= 1
        assert any(c.name == "OrderController" for c in classes)

    def test_class_fqn(self, order_controller_index):
        cls = next(s for s in order_controller_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "OrderController")
        assert cls.fully_qualified_name == "MyApp.Controllers.OrderController"

    def test_class_attributes(self, order_controller_index):
        cls = next(s for s in order_controller_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "OrderController")
        attr_names = [a.name for a in cls.annotations]
        assert "ApiController" in attr_names
        assert "Route" in attr_names

    def test_route_attribute_argument(self, order_controller_index):
        cls = next(s for s in order_controller_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "OrderController")
        route = next(a for a in cls.annotations if a.name == "Route")
        # Should capture the route template
        assert len(route.arguments) > 0

    def test_class_extends(self, order_controller_index):
        cls = next(s for s in order_controller_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "OrderController")
        assert cls.extends is not None
        assert "ControllerBase" in cls.extends

    def test_class_has_docstring(self, order_controller_index):
        cls = next(s for s in order_controller_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "OrderController")
        assert cls.docstring is not None
        assert "order" in cls.docstring.lower()


# ======================================================================
# Interface extraction
# ======================================================================


class TestInterfaceExtraction:
    def test_interface_found(self, iorder_service_index):
        interfaces = [s for s in iorder_service_index.symbols if s.kind == SymbolKind.INTERFACE]
        assert len(interfaces) >= 1
        assert any(i.name == "IOrderService" for i in interfaces)

    def test_interface_fqn(self, iorder_service_index):
        iface = next(s for s in iorder_service_index.symbols
                     if s.kind == SymbolKind.INTERFACE and s.name == "IOrderService")
        assert iface.fully_qualified_name == "MyApp.Services.IOrderService"

    def test_interface_methods(self, iorder_service_index):
        methods = [s for s in iorder_service_index.symbols if s.kind == SymbolKind.METHOD]
        method_names = [m.name for m in methods]
        assert any("GetByIdAsync" in n for n in method_names)
        assert any("CreateAsync" in n for n in method_names)


# ======================================================================
# Enum extraction
# ======================================================================


class TestEnumExtraction:
    def test_enum_found(self, order_status_index):
        enums = [s for s in order_status_index.symbols if s.kind == SymbolKind.ENUM]
        assert len(enums) >= 1
        assert any(e.name == "OrderStatus" for e in enums)

    def test_enum_fqn(self, order_status_index):
        enum = next(s for s in order_status_index.symbols if s.kind == SymbolKind.ENUM)
        assert enum.fully_qualified_name == "MyApp.Models.OrderStatus"

    def test_enum_docstring(self, order_status_index):
        enum = next(s for s in order_status_index.symbols if s.kind == SymbolKind.ENUM)
        assert enum.docstring is not None
        assert "status" in enum.docstring.lower()


# ======================================================================
# Method extraction
# ======================================================================


class TestMethodExtraction:
    def test_methods_found(self, order_controller_index):
        methods = [s for s in order_controller_index.symbols if s.kind == SymbolKind.METHOD]
        method_names = [m.name for m in methods]
        assert any("GetOrder" in n for n in method_names)
        assert any("CreateOrder" in n for n in method_names)

    def test_async_method(self, order_controller_index):
        get_order = next(s for s in order_controller_index.symbols
                         if s.kind == SymbolKind.METHOD and "GetOrder" in s.name)
        assert get_order.signature is not None
        assert get_order.signature.is_async is True

    def test_method_return_type(self, order_controller_index):
        get_order = next(s for s in order_controller_index.symbols
                         if s.kind == SymbolKind.METHOD and "GetOrder" in s.name)
        assert get_order.signature.return_type is not None
        assert "Task" in get_order.signature.return_type

    def test_method_parameters(self, order_controller_index):
        get_order = next(s for s in order_controller_index.symbols
                         if s.kind == SymbolKind.METHOD and "GetOrder" in s.name)
        assert len(get_order.signature.parameters) == 1
        assert get_order.signature.parameters[0].name == "id"

    def test_method_xml_doc(self, order_controller_index):
        get_order = next(s for s in order_controller_index.symbols
                         if s.kind == SymbolKind.METHOD and "GetOrder" in s.name)
        assert get_order.docstring is not None
        assert "retrieves" in get_order.docstring.lower() or "order" in get_order.docstring.lower()

    def test_method_attributes(self, order_controller_index):
        get_order = next(s for s in order_controller_index.symbols
                         if s.kind == SymbolKind.METHOD and "GetOrder" in s.name)
        attr_names = [a.name for a in get_order.annotations]
        assert "HttpGet" in attr_names

    def test_method_parent(self, order_controller_index):
        get_order = next(s for s in order_controller_index.symbols
                         if s.kind == SymbolKind.METHOD and "GetOrder" in s.name)
        assert get_order.parent_symbol_id == "MyApp.Controllers.OrderController"

    def test_private_method(self, order_service_index):
        map_method = next(
            (s for s in order_service_index.symbols
             if s.kind == SymbolKind.METHOD and "MapToDto" in s.name),
            None,
        )
        assert map_method is not None
        assert "private" in map_method.modifiers


# ======================================================================
# Constructor extraction
# ======================================================================


class TestConstructorExtraction:
    def test_constructor_found(self, order_controller_index):
        ctors = [s for s in order_controller_index.symbols if s.kind == SymbolKind.CONSTRUCTOR]
        assert len(ctors) >= 1

    def test_constructor_parameters(self, order_controller_index):
        ctor = next(s for s in order_controller_index.symbols if s.kind == SymbolKind.CONSTRUCTOR)
        assert ctor.signature is not None
        assert len(ctor.signature.parameters) == 2


# ======================================================================
# Property extraction (C#-specific)
# ======================================================================


class TestPropertyExtraction:
    def test_properties_found(self, order_service_index):
        props = [s for s in order_service_index.symbols if s.kind == SymbolKind.PROPERTY]
        assert len(props) >= 2

    def test_property_get_set(self, order_service_index):
        max_retries = next(
            s for s in order_service_index.symbols
            if s.kind == SymbolKind.PROPERTY and "MaxRetries" in s.name
        )
        assert max_retries.property_accessors is not None
        assert max_retries.property_accessors.has_getter is True
        assert max_retries.property_accessors.has_setter is True

    def test_property_get_init(self, order_service_index):
        svc_name = next(
            s for s in order_service_index.symbols
            if s.kind == SymbolKind.PROPERTY and "ServiceName" in s.name
        )
        assert svc_name.property_accessors is not None
        assert svc_name.property_accessors.has_getter is True
        assert svc_name.property_accessors.has_init is True

    def test_property_type(self, order_service_index):
        max_retries = next(
            s for s in order_service_index.symbols
            if s.kind == SymbolKind.PROPERTY and "MaxRetries" in s.name
        )
        assert max_retries.field_type == "int"

    def test_property_docstring(self, order_service_index):
        max_retries = next(
            s for s in order_service_index.symbols
            if s.kind == SymbolKind.PROPERTY and "MaxRetries" in s.name
        )
        assert max_retries.docstring is not None
        assert "retries" in max_retries.docstring.lower()


# ======================================================================
# Field extraction
# ======================================================================


class TestFieldExtraction:
    def test_fields_found(self, order_controller_index):
        fields = [s for s in order_controller_index.symbols if s.kind == SymbolKind.FIELD]
        assert len(fields) >= 1

    def test_field_modifiers(self, order_controller_index):
        fields = [s for s in order_controller_index.symbols if s.kind == SymbolKind.FIELD]
        order_svc_field = next(
            (f for f in fields if "_orderservice" in f.name.lower()),
            None,
        )
        assert order_svc_field is not None
        assert "private" in order_svc_field.modifiers
        assert "readonly" in order_svc_field.modifiers


# ======================================================================
# Service class with inheritance
# ======================================================================


class TestServiceInheritance:
    def test_service_implements(self, order_service_index):
        cls = next(s for s in order_service_index.symbols
                   if s.kind == SymbolKind.CLASS and s.name == "OrderService")
        assert len(cls.implements) >= 1
        impl_names = [i.split(".")[-1] for i in cls.implements]
        assert "IOrderService" in impl_names or "IAuditable" in impl_names
