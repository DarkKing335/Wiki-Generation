"""C# AST parser using tree-sitter-c-sharp.

Implements US-1.4 — C# AST Parsing.  Extracts:

* Namespaces & using directives (including aliases, static usings)
* Classes, structs, interfaces, enums, records, delegates
* Attributes with arguments ([ApiController], [HttpGet], …)
* Properties with accessor info ({ get; set; })
* Fields with modifiers
* Methods: async status, parameters (ref, out, in), XML doc comments
* Constructors
* Inheritance / implementation relationships
* Method invocations (call-graph edges)

Reference
---------
* ``docs/designs/ast-parser-design.md`` — Section 5 (C# Parser)
* ``docs/user-stories.md`` — US-1.4
* CodeWiki reference: ``research/projects/CodeWiki/…/analyzers/csharp.py``
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from tree_sitter import Language as TSLanguage, Parser
import tree_sitter_c_sharp

from core_indexing.models import (
    ASTSymbolNode,
    AnnotationInfo,
    FileIndex,
    ImportInfo,
    Language,
    MethodSignature,
    ParameterInfo,
    PropertyAccessors,
    RelationshipEdge,
    SourceRange,
    SymbolKind,
)
from core_indexing.parsers.base import BaseLanguageParser

logger = logging.getLogger(__name__)

# C# type declarations that introduce a named scope
_TYPE_DECLS = {
    "class_declaration",
    "interface_declaration",
    "struct_declaration",
    "enum_declaration",
    "record_declaration",
}

# C# primitives — never project symbols
_CSHARP_PRIMITIVES = {
    "bool", "byte", "sbyte", "char", "decimal", "double", "float", "int",
    "uint", "nint", "nuint", "long", "ulong", "short", "ushort", "string",
    "object", "void", "var", "dynamic",
}

# .NET framework prefixes — external types
_CSHARP_EXTERNAL_PREFIXES = (
    "System.", "Microsoft.", "Newtonsoft.", "NUnit.",
)


class CSharpParser(BaseLanguageParser):
    """Tree-sitter based C# AST parser producing normalised ``ASTSymbolNode`` instances."""

    @property
    def language(self) -> Language:
        return Language.CSHARP

    @property
    def file_extensions(self) -> Tuple[str, ...]:
        return (".cs",)

    def parse(self, file_path: str, content: str, repo_path: str = "") -> FileIndex:
        rel_path = self._relative_path(file_path, repo_path)
        ctx = _CSharpParseContext(content, file_path, repo_path, rel_path)
        return ctx.file_index


# ======================================================================
# Internal parse context
# ======================================================================


class _CSharpParseContext:
    """Encapsulates the stateful parsing of a single C# file."""

    def __init__(self, content: str, file_path: str, repo_path: str, rel_path: str):
        self.content = content
        self.file_path = file_path
        self.repo_path = repo_path
        self.rel_path = rel_path
        self.lines = content.splitlines()

        # Extracted data
        self.file_scoped_namespace: str = ""
        self.using_namespaces: List[str] = []
        self.alias_map: Dict[str, str] = {}
        self.static_usings: List[str] = []
        self.import_infos: List[ImportInfo] = []
        self.symbols: List[ASTSymbolNode] = []
        self.relationships: List[RelationshipEdge] = []
        self._symbol_lookup: Dict[str, ASTSymbolNode] = {}

        self._do_parse()

    @property
    def file_index(self) -> FileIndex:
        return FileIndex(
            file_path=self.rel_path,
            language=Language.CSHARP,
            package_or_namespace=self.file_scoped_namespace or None,
            imports=self.import_infos,
            symbols=self.symbols,
        )

    # ------------------------------------------------------------------
    # Parse pipeline
    # ------------------------------------------------------------------

    def _do_parse(self):
        lang_capsule = tree_sitter_c_sharp.language()
        ts_lang = TSLanguage(lang_capsule)
        parser = Parser(ts_lang)
        tree = parser.parse(bytes(self.content, "utf-8"))
        root = tree.root_node

        self._extract_usings(root)
        self._extract_nodes(root, parent_fqn=None)
        self._extract_relationships(root)

    # ------------------------------------------------------------------
    # Using directives & namespaces
    # ------------------------------------------------------------------

    def _extract_usings(self, node):
        if node.type == "file_scoped_namespace_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                self.file_scoped_namespace = name_node.text.decode()

        elif node.type == "using_directive":
            children = [c for c in node.children if c.type not in ("using", ";", "global")]
            has_static = any(c.type == "static" for c in node.children)
            has_alias = any(c.type == "=" for c in node.children)
            name_children = [c for c in children if c.type in ("identifier", "qualified_name")]

            if has_alias and len(name_children) >= 2:
                alias_name = name_children[0].text.decode()
                target_name = name_children[1].text.decode()
                self.alias_map[alias_name] = target_name
                self.import_infos.append(ImportInfo(
                    name=target_name, alias=alias_name,
                ))
            elif has_static and name_children:
                static_name = name_children[-1].text.decode()
                self.static_usings.append(static_name)
                self.import_infos.append(ImportInfo(
                    name=static_name, is_static=True,
                ))
            elif name_children:
                ns_name = name_children[-1].text.decode()
                self.using_namespaces.append(ns_name)
                self.import_infos.append(ImportInfo(name=ns_name))

        for child in node.children:
            self._extract_usings(child)

    def _namespace_for(self, node) -> str:
        parts = []
        current = node
        while current:
            if current.type == "namespace_declaration":
                name_node = current.child_by_field_name("name")
                if name_node:
                    parts.append(name_node.text.decode())
            current = current.parent
        parts.reverse()
        if self.file_scoped_namespace:
            parts.insert(0, self.file_scoped_namespace)
        return ".".join(p for p in parts if p)

    def _qualify(self, node, *names) -> str:
        ns = self._namespace_for(node)
        parts = [ns] if ns else []
        parts.extend(n for n in names if n)
        return ".".join(parts)

    # ------------------------------------------------------------------
    # Node extraction
    # ------------------------------------------------------------------

    _TYPE_MAP = {
        "class_declaration": SymbolKind.CLASS,
        "interface_declaration": SymbolKind.INTERFACE,
        "struct_declaration": SymbolKind.STRUCT,
        "enum_declaration": SymbolKind.ENUM,
        "record_declaration": SymbolKind.RECORD,
        "delegate_declaration": SymbolKind.DELEGATE,
    }

    def _extract_nodes(self, node, parent_fqn: Optional[str]):
        kind: Optional[SymbolKind] = None
        name: Optional[str] = None
        fqn: Optional[str] = None
        parent_sym_id: Optional[str] = None

        # --- Type declarations ---
        if node.type in self._TYPE_MAP:
            kind = self._TYPE_MAP[node.type]
            decl_name = self._decl_name(node)
            if decl_name:
                name = decl_name
                containing = self._find_containing_type_names(node)
                fqn = self._qualify(node, *containing, name)
                parent_sym_id = parent_fqn

        # --- Method declarations ---
        elif node.type == "method_declaration":
            method_name = self._decl_name(node)
            if method_name:
                containing = self._find_containing_type_names(node)
                if containing:
                    name = f"{containing[-1]}.{method_name}"
                    fqn = self._qualify(node, *containing, method_name)
                    parent_sym_id = self._qualify(node, *containing)
                else:
                    name = method_name
                    fqn = self._qualify(node, method_name)
                    parent_sym_id = parent_fqn
                kind = SymbolKind.METHOD

        # --- Constructor declarations ---
        elif node.type == "constructor_declaration":
            ctor_name = self._decl_name(node)
            if ctor_name:
                containing = self._find_containing_type_names(node)
                name = f"{ctor_name}.<init>"
                fqn = self._qualify(node, *containing, "<init>")
                parent_sym_id = self._qualify(node, *containing) if containing else parent_fqn
                kind = SymbolKind.CONSTRUCTOR

        # --- Property declarations ---
        elif node.type == "property_declaration":
            self._extract_property(node, parent_fqn)
            return

        # --- Field declarations ---
        elif node.type == "field_declaration":
            self._extract_field(node, parent_fqn)
            return

        if kind and name and fqn:
            symbol = self._build_symbol(node, kind, name, fqn, parent_sym_id)
            self.symbols.append(symbol)
            self._symbol_lookup[fqn] = symbol
            self._symbol_lookup[name] = symbol

            new_parent = fqn if kind in (
                SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.STRUCT,
                SymbolKind.ENUM, SymbolKind.RECORD, SymbolKind.DELEGATE,
            ) else parent_fqn
            for child in node.children:
                self._extract_nodes(child, parent_fqn=new_parent)
        else:
            for child in node.children:
                self._extract_nodes(child, parent_fqn=parent_fqn)

    def _extract_property(self, node, parent_fqn: Optional[str]):
        prop_name_node = node.child_by_field_name("name")
        if not prop_name_node:
            return
        prop_name = prop_name_node.text.decode()
        containing = self._find_containing_type_names(node)
        name = f"{containing[-1]}.{prop_name}" if containing else prop_name
        fqn = self._qualify(node, *containing, prop_name)

        # Type
        type_node = node.child_by_field_name("type")
        field_type = type_node.text.decode() if type_node else None

        # Accessors
        accessors = self._parse_accessors(node)

        symbol = ASTSymbolNode(
            symbol_id=fqn,
            language=Language.CSHARP,
            kind=SymbolKind.PROPERTY,
            name=name,
            fully_qualified_name=fqn,
            file_path=self.rel_path,
            range=SourceRange(
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            ),
            modifiers=self._collect_modifiers(node),
            annotations=self._collect_attributes(node),
            docstring=self._extract_xml_doc(node),
            parent_symbol_id=(
                self._qualify(node, *containing) if containing else parent_fqn
            ),
            field_type=field_type,
            property_accessors=accessors,
        )
        self.symbols.append(symbol)
        self._symbol_lookup[fqn] = symbol

    def _extract_field(self, node, parent_fqn: Optional[str]):
        containing = self._find_containing_type_names(node)
        modifiers = self._collect_modifiers(node)
        annotations = self._collect_attributes(node)
        docstring = self._extract_xml_doc(node)

        # Get type from variable_declaration
        var_decl = next((c for c in node.children if c.type == "variable_declaration"), None)
        field_type = None
        if var_decl:
            type_node = next(
                (c for c in var_decl.children if c.type not in (
                    "variable_declarator", ",", ";"
                )),
                None,
            )
            if type_node:
                field_type = type_node.text.decode()

            for child in var_decl.children:
                if child.type == "variable_declarator":
                    ident = next(
                        (c for c in child.children if c.type == "identifier"),
                        None,
                    )
                    if not ident:
                        continue
                    field_name = ident.text.decode()
                    name = f"{containing[-1]}.{field_name}" if containing else field_name
                    fqn = self._qualify(node, *containing, field_name)

                    symbol = ASTSymbolNode(
                        symbol_id=fqn,
                        language=Language.CSHARP,
                        kind=SymbolKind.FIELD,
                        name=name,
                        fully_qualified_name=fqn,
                        file_path=self.rel_path,
                        range=SourceRange(
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                        ),
                        modifiers=modifiers,
                        annotations=annotations,
                        docstring=docstring,
                        parent_symbol_id=(
                            self._qualify(node, *containing) if containing else parent_fqn
                        ),
                        field_type=field_type,
                    )
                    self.symbols.append(symbol)
                    self._symbol_lookup[fqn] = symbol

    # ------------------------------------------------------------------
    # Property accessors
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_accessors(node) -> PropertyAccessors:
        has_getter = False
        has_setter = False
        has_init = False

        accessor_list = next(
            (c for c in node.children if c.type == "accessor_list"),
            None,
        )
        if accessor_list:
            for acc in accessor_list.children:
                if acc.type == "accessor_declaration":
                    keyword = next(
                        (c for c in acc.children if c.type in ("get", "set", "init")),
                        None,
                    )
                    if keyword:
                        text = keyword.type
                        if text == "get":
                            has_getter = True
                        elif text == "set":
                            has_setter = True
                        elif text == "init":
                            has_init = True

        return PropertyAccessors(
            has_getter=has_getter,
            has_setter=has_setter,
            has_init=has_init,
        )

    # ------------------------------------------------------------------
    # Symbol builder
    # ------------------------------------------------------------------

    def _build_symbol(
        self,
        node,
        kind: SymbolKind,
        name: str,
        fqn: str,
        parent_sym_id: Optional[str],
    ) -> ASTSymbolNode:
        modifiers = self._collect_modifiers(node)
        annotations = self._collect_attributes(node)
        docstring = self._extract_xml_doc(node)

        signature: Optional[MethodSignature] = None
        if kind in (SymbolKind.METHOD, SymbolKind.CONSTRUCTOR):
            signature = self._build_method_signature(node, kind, modifiers)

        extends = None
        implements_list: List[str] = []
        if kind in (SymbolKind.CLASS, SymbolKind.STRUCT, SymbolKind.RECORD):
            base_types = self._extract_base_types(node)
            if base_types:
                # In C#, the first base type could be a class or interface
                # Convention: treat the first PascalCase non-I-prefixed as extends
                first = base_types[0]
                if not first.startswith("I") or (len(first) > 1 and not first[1].isupper()):
                    extends = self._resolve_type(first, node)
                    implements_list = [self._resolve_type(t, node) for t in base_types[1:]]
                else:
                    implements_list = [self._resolve_type(t, node) for t in base_types]
        elif kind == SymbolKind.INTERFACE:
            base_types = self._extract_base_types(node)
            implements_list = [self._resolve_type(t, node) for t in base_types]

        return ASTSymbolNode(
            symbol_id=fqn,
            language=Language.CSHARP,
            kind=kind,
            name=name,
            fully_qualified_name=fqn,
            file_path=self.rel_path,
            range=SourceRange(
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
            ),
            modifiers=modifiers,
            annotations=annotations,
            docstring=docstring,
            parent_symbol_id=parent_sym_id,
            signature=signature,
            extends=extends,
            implements=implements_list,
        )

    # ------------------------------------------------------------------
    # Modifiers
    # ------------------------------------------------------------------

    _MODIFIER_KEYWORDS = {
        "public", "private", "protected", "internal", "static", "readonly",
        "sealed", "abstract", "virtual", "override", "new", "partial",
        "async", "extern", "volatile", "unsafe", "const", "ref",
    }

    def _collect_modifiers(self, node) -> List[str]:
        mods = []
        for child in node.children:
            if child.type == "modifier":
                text = child.text.decode()
                if text in self._MODIFIER_KEYWORDS:
                    mods.append(text)
        return mods

    # ------------------------------------------------------------------
    # Attributes (C# equivalent of Java annotations)
    # ------------------------------------------------------------------

    def _collect_attributes(self, node) -> List[AnnotationInfo]:
        attrs = []
        for child in node.children:
            if child.type == "attribute_list":
                for attr_child in child.children:
                    if attr_child.type == "attribute":
                        attrs.append(self._parse_attribute(attr_child))
        return attrs

    @staticmethod
    def _parse_attribute(attr_node) -> AnnotationInfo:
        name = ""
        args: Dict[str, str] = {}

        name_node = attr_node.child_by_field_name("name")
        if name_node:
            name = name_node.text.decode()

        arg_list = next(
            (c for c in attr_node.children if c.type == "attribute_argument_list"),
            None,
        )
        if arg_list:
            positional_idx = 0
            for arg_child in arg_list.children:
                if arg_child.type == "attribute_argument":
                    name_colon = arg_child.child_by_field_name("name")
                    expr = arg_child.child_by_field_name("expression")
                    if name_colon and expr:
                        args[name_colon.text.decode()] = expr.text.decode().strip('"')
                    elif expr:
                        args["value"] = expr.text.decode().strip('"')
                    else:
                        # Fallback: just get the text content
                        text = arg_child.text.decode().strip('"')
                        if "=" in text:
                            key, _, val = text.partition("=")
                            args[key.strip()] = val.strip().strip('"')
                        else:
                            args[f"arg{positional_idx}"] = text
                            positional_idx += 1

        return AnnotationInfo(name=name, arguments=args)

    # ------------------------------------------------------------------
    # XML doc comments
    # ------------------------------------------------------------------

    def _extract_xml_doc(self, node) -> Optional[str]:
        comments = []
        sib = node.prev_sibling
        while sib is not None:
            if sib.type == "attribute_list":
                sib = sib.prev_sibling
                continue
            if sib.type == "comment" and sib.text.decode().lstrip().startswith("///"):
                comments.append(sib.text.decode())
                sib = sib.prev_sibling
                continue
            break
        if not comments:
            return None
        comments.reverse()
        return BaseLanguageParser._clean_xml_doc(comments)

    # ------------------------------------------------------------------
    # Method / constructor signature
    # ------------------------------------------------------------------

    def _build_method_signature(
        self, node, kind: SymbolKind, modifiers: List[str]
    ) -> MethodSignature:
        return_type = None
        params: List[ParameterInfo] = []
        is_async = "async" in modifiers

        if kind == SymbolKind.METHOD:
            ret_node = node.child_by_field_name("type")
            if ret_node:
                return_type = ret_node.text.decode()
            else:
                # Find type node before the method identifier
                name_node = node.child_by_field_name("name")
                for child in node.children:
                    if name_node and child == name_node:
                        break
                    if child.type not in ("attribute_list", "modifier"):
                        return_type = child.text.decode()
                        break

        param_list = next(
            (c for c in node.children if c.type == "parameter_list"),
            None,
        )
        if param_list:
            for param in param_list.children:
                if param.type == "parameter":
                    p_name_node = param.child_by_field_name("name")
                    p_type_node = param.child_by_field_name("type")
                    if p_name_node:
                        p_mods = []
                        # Check for ref, out, in, params modifiers
                        for pc in param.children:
                            if pc.type in ("ref", "out", "in", "params", "this"):
                                p_mods.append(pc.type)
                        params.append(ParameterInfo(
                            name=p_name_node.text.decode(),
                            type=p_type_node.text.decode() if p_type_node else "unknown",
                            modifiers=p_mods,
                        ))

        return MethodSignature(
            return_type=return_type,
            parameters=params,
            is_async=is_async,
        )

    # ------------------------------------------------------------------
    # Base types (inheritance / implementation)
    # ------------------------------------------------------------------

    def _extract_base_types(self, node) -> List[str]:
        base_list = next((c for c in node.children if c.type == "base_list"), None)
        if not base_list:
            return []
        types = []
        for child in base_list.children:
            name = self._unwrap_type(child)
            if name:
                types.append(name)
            elif child.type == "primary_constructor_base_type":
                inner = next(
                    (c for c in child.children if c.type in ("identifier", "qualified_name", "generic_name")),
                    None,
                )
                if inner:
                    n = self._unwrap_type(inner)
                    if n:
                        types.append(n)
        return types

    # ------------------------------------------------------------------
    # Relationship extraction
    # ------------------------------------------------------------------

    def _extract_relationships(self, node):
        if node.type in _TYPE_DECLS:
            type_name = self._decl_name(node)
            if type_name:
                containing = self._find_containing_type_names(node)
                fqn = self._qualify(node, *containing, type_name)
                base_types = self._extract_base_types(node)
                for bt in base_types:
                    resolved = self._resolve_type(bt, node)
                    if not self._is_external(resolved):
                        kind = "implements" if bt.startswith("I") and len(bt) > 1 and bt[1].isupper() else "extends"
                        self.relationships.append(RelationshipEdge(
                            source=fqn, target=resolved, kind=kind,
                            line=node.start_point[0] + 1,
                        ))

        if node.type == "invocation_expression":
            self._handle_invocation(node)

        if node.type == "object_creation_expression":
            self._handle_object_creation(node)

        for child in node.children:
            self._extract_relationships(child)

    def _handle_invocation(self, node):
        caller = self._find_enclosing_method_fqn(node) or self._find_enclosing_type_fqn(node)
        if not caller:
            return

        func = node.child_by_field_name("function")
        if not func:
            return

        method_name = None
        target_type = None

        if func.type == "identifier":
            method_name = func.text.decode()
            containing = self._find_enclosing_type_fqn(node)
            if containing:
                callee = f"{containing}.{method_name}"
                self.relationships.append(RelationshipEdge(
                    source=caller, target=callee, kind="calls",
                    line=node.start_point[0] + 1,
                ))
        elif func.type == "member_access_expression":
            name_node = func.child_by_field_name("name")
            if name_node and name_node.type == "identifier":
                method_name = name_node.text.decode()
                expr = func.child_by_field_name("expression")
                if expr and expr.type == "identifier":
                    receiver = expr.text.decode()
                    if receiver[0:1].isupper():
                        target_type = self._resolve_type(receiver, node)
                        if target_type and not self._is_external(target_type):
                            callee = f"{target_type}.{method_name}"
                            self.relationships.append(RelationshipEdge(
                                source=caller, target=callee, kind="calls",
                                line=node.start_point[0] + 1,
                            ))

    def _handle_object_creation(self, node):
        caller = self._find_enclosing_type_fqn(node)
        if not caller:
            return
        type_node = node.child_by_field_name("type")
        if type_node:
            created = self._unwrap_type(type_node)
            if created:
                resolved = self._resolve_type(created, node)
                if not self._is_external(resolved):
                    self.relationships.append(RelationshipEdge(
                        source=caller, target=resolved, kind="instantiates",
                        line=node.start_point[0] + 1,
                    ))

    # ------------------------------------------------------------------
    # Type resolution helpers
    # ------------------------------------------------------------------

    def _resolve_type(self, type_name: str, context_node) -> str:
        simple = type_name.split("<", 1)[0].strip()
        if "." in simple:
            return simple
        if simple in self.alias_map:
            return self.alias_map[simple]
        containing = self._find_containing_type_names(context_node)
        for idx in range(len(containing), 0, -1):
            candidate = self._qualify(context_node, *containing[:idx], simple)
            if candidate in self._symbol_lookup:
                return candidate
        for namespace in self.using_namespaces:
            candidate = f"{namespace}.{simple}"
            if candidate in self._symbol_lookup:
                return candidate
        # If we have a namespace, qualify with it
        ns = self._namespace_for(context_node)
        if ns:
            return f"{ns}.{simple}"
        return simple

    @staticmethod
    def _is_external(fqn: str) -> bool:
        simple = fqn.split(".")[-1] if "." in fqn else fqn
        if simple in _CSHARP_PRIMITIVES:
            return True
        for prefix in _CSHARP_EXTERNAL_PREFIXES:
            if fqn.startswith(prefix):
                return True
        return False

    def _find_enclosing_type_fqn(self, node) -> Optional[str]:
        names = self._find_containing_type_names(node)
        if names:
            return self._qualify(node, *names)
        return None

    def _find_enclosing_method_fqn(self, node) -> Optional[str]:
        current = node.parent
        while current:
            if current.type == "method_declaration":
                method_name = self._decl_name(current)
                containing = self._find_containing_type_names(current)
                if method_name and containing:
                    return self._qualify(current, *containing, method_name)
            current = current.parent
        return None

    # ------------------------------------------------------------------
    # Tree-sitter helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unwrap_type(node) -> Optional[str]:
        if node is None:
            return None
        if node.type in ("identifier", "qualified_name", "predefined_type"):
            return node.text.decode()
        if node.type == "generic_name":
            ident = next((c for c in node.children if c.type == "identifier"), None)
            return ident.text.decode() if ident else None
        if node.type in ("nullable_type", "array_type", "pointer_type"):
            inner = node.child_by_field_name("type")
            if inner is None:
                inner = next(
                    (c for c in node.children if c.type in (
                        "identifier", "qualified_name", "generic_name", "predefined_type",
                    )),
                    None,
                )
            return _CSharpParseContext._unwrap_type(inner)
        return None

    @staticmethod
    def _decl_name(node) -> Optional[str]:
        name_node = node.child_by_field_name("name")
        return name_node.text.decode() if name_node else None

    @staticmethod
    def _find_containing_type_names(node) -> List[str]:
        names = []
        current = node.parent
        while current:
            if current.type in _TYPE_DECLS:
                name_node = current.child_by_field_name("name")
                if name_node:
                    names.append(name_node.text.decode())
            current = current.parent
        return list(reversed(names))
