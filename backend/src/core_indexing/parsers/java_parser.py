"""Java AST parser using tree-sitter-java.

Implements US-1.3 — Java AST Parsing.  Extracts:

* Packages & imports (explicit and wildcard)
* Classes, interfaces, enums, records, annotation types
* Annotations with arguments (@RestController, @Service, …)
* Fields: name, type, visibility modifiers, static/final
* Methods: signature, return type, parameters, thrown exceptions,
  access modifiers, Javadoc, line numbers
* Constructors
* Inheritance relationships (extends, implements)
* Method invocations (call-graph edges)

Reference
---------
* ``docs/designs/ast-parser-design.md`` — Section 4 (Java Parser)
* ``docs/user-stories.md`` — US-1.3
* CodeWiki reference: ``research/projects/CodeWiki/…/analyzers/java.py``
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from tree_sitter import Language as TSLanguage, Parser
import tree_sitter_java

from core_indexing.models import (
    ASTSymbolNode,
    AnnotationInfo,
    FileIndex,
    ImportInfo,
    Language,
    MethodSignature,
    ParameterInfo,
    RelationshipEdge,
    SourceRange,
    SymbolKind,
)
from core_indexing.parsers.base import BaseLanguageParser

logger = logging.getLogger(__name__)

# Java primitive & boxing types that are never project symbols
_JAVA_PRIMITIVES = {
    "boolean", "byte", "char", "double", "float", "int", "long", "short",
    "void", "var",
    # Boxed wrappers & common JDK types
    "Boolean", "Byte", "Character", "Double", "Float", "Integer", "Long",
    "Short", "Void", "String", "Object",
}

# Common JDK package prefixes — types from these are external
_JAVA_EXTERNAL_PREFIXES = (
    "java.", "javax.", "sun.", "com.sun.", "jdk.",
    "org.w3c.", "org.xml.", "org.ietf.",
)


class JavaParser(BaseLanguageParser):
    """Tree-sitter based Java AST parser producing normalised ``ASTSymbolNode`` instances."""

    @property
    def language(self) -> Language:
        return Language.JAVA

    @property
    def file_extensions(self) -> Tuple[str, ...]:
        return (".java",)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, file_path: str, content: str, repo_path: str = "") -> FileIndex:
        rel_path = self._relative_path(file_path, repo_path)
        ctx = _JavaParseContext(content, file_path, repo_path, rel_path)
        return ctx.file_index


# ======================================================================
# Internal parse context (stateful, single-file lifetime)
# ======================================================================


class _JavaParseContext:
    """Encapsulates the stateful parsing of a single Java file."""

    def __init__(self, content: str, file_path: str, repo_path: str, rel_path: str):
        self.content = content
        self.file_path = file_path
        self.repo_path = repo_path
        self.rel_path = rel_path
        self.lines = content.splitlines()

        # Extracted data
        self.package_name: str = ""
        self.import_map: Dict[str, str] = {}
        self.wildcard_imports: List[str] = []
        self.import_infos: List[ImportInfo] = []
        self.symbols: List[ASTSymbolNode] = []
        self.relationships: List[RelationshipEdge] = []
        self._symbol_lookup: Dict[str, ASTSymbolNode] = {}

        # Parse
        self._do_parse()

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    @property
    def file_index(self) -> FileIndex:
        return FileIndex(
            file_path=self.rel_path,
            language=Language.JAVA,
            package_or_namespace=self.package_name or None,
            imports=self.import_infos,
            symbols=self.symbols,
        )

    # ------------------------------------------------------------------
    # Parsing pipeline
    # ------------------------------------------------------------------

    def _do_parse(self):
        lang_capsule = tree_sitter_java.language()
        ts_lang = TSLanguage(lang_capsule)
        parser = Parser(ts_lang)
        tree = parser.parse(bytes(self.content, "utf-8"))
        root = tree.root_node

        self._extract_package(root)
        self._extract_imports(root)
        self._extract_nodes(root, parent_fqn=None)
        self._extract_relationships(root)

    # ------------------------------------------------------------------
    # Package & imports
    # ------------------------------------------------------------------

    def _extract_package(self, root):
        for child in root.children:
            if child.type == "package_declaration":
                name_node = self._find_child_by_types(child, ("scoped_identifier", "identifier"))
                if name_node:
                    self.package_name = name_node.text.decode()
                break

    def _extract_imports(self, root):
        for child in root.children:
            if child.type == "import_declaration":
                is_static = any(c.type == "static" for c in child.children)
                name_node = self._find_child_by_types(child, ("scoped_identifier", "identifier"))
                if not name_node:
                    continue
                full_name = name_node.text.decode()

                # Check for wildcard
                is_wildcard = any(
                    c.type == "asterisk" for c in child.children
                )
                if is_wildcard:
                    self.wildcard_imports.append(full_name)
                    self.import_infos.append(ImportInfo(
                        name=full_name + ".*",
                        is_wildcard=True,
                        is_static=is_static,
                    ))
                else:
                    simple_name = full_name.rsplit(".", 1)[-1]
                    self.import_map[simple_name] = full_name
                    self.import_infos.append(ImportInfo(
                        name=full_name,
                        is_wildcard=False,
                        is_static=is_static,
                    ))

    # ------------------------------------------------------------------
    # Node extraction
    # ------------------------------------------------------------------

    _TYPE_DECLARATIONS = {
        "class_declaration": SymbolKind.CLASS,
        "interface_declaration": SymbolKind.INTERFACE,
        "enum_declaration": SymbolKind.ENUM,
        "record_declaration": SymbolKind.RECORD,
        "annotation_type_declaration": SymbolKind.ANNOTATION,
    }

    def _extract_nodes(self, node, parent_fqn: Optional[str]):
        kind: Optional[SymbolKind] = None
        name: Optional[str] = None
        fqn: Optional[str] = None
        parent_sym_id: Optional[str] = None

        # --- Type declarations ---
        if node.type in self._TYPE_DECLARATIONS:
            kind = self._TYPE_DECLARATIONS[node.type]
            # Detect abstract class
            if node.type == "class_declaration":
                if self._has_modifier(node, "abstract"):
                    pass  # kind stays CLASS, modifiers will contain 'abstract'
            name_node = self._get_identifier(node)
            if name_node:
                name = name_node.text.decode()
                containing = self._find_containing_type_names(node)
                fqn = self._qualify_name(".".join([*containing, name]))
                parent_sym_id = parent_fqn

        # --- Method declarations ---
        elif node.type == "method_declaration":
            name_node = self._get_identifier(node)
            if name_node:
                method_name = name_node.text.decode()
                containing = self._find_containing_type_names(node)
                if containing:
                    name = f"{containing[-1]}.{method_name}"
                    fqn = self._qualify_name(".".join([*containing, method_name]))
                    parent_sym_id = self._qualify_name(".".join(containing))
                else:
                    name = method_name
                    fqn = self._qualify_name(method_name)
                    parent_sym_id = parent_fqn
                kind = SymbolKind.METHOD

        # --- Constructor declarations ---
        elif node.type == "constructor_declaration":
            name_node = self._get_identifier(node)
            if name_node:
                ctor_name = name_node.text.decode()
                containing = self._find_containing_type_names(node)
                name = f"{ctor_name}.<init>"
                fqn = self._qualify_name(".".join([*containing, "<init>"]))
                parent_sym_id = self._qualify_name(".".join(containing)) if containing else parent_fqn
                kind = SymbolKind.CONSTRUCTOR

        # --- Field declarations ---
        elif node.type == "field_declaration":
            self._extract_field_nodes(node, parent_fqn)
            # Recurse into children (e.g., annotations on fields)
            # but field_declaration itself doesn't recurse further
            return

        if kind and name and fqn:
            symbol = self._build_symbol(node, kind, name, fqn, parent_sym_id)
            self.symbols.append(symbol)
            self._symbol_lookup[fqn] = symbol
            self._symbol_lookup[name] = symbol

            # Recurse with updated parent
            new_parent = fqn if kind in (
                SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.ENUM,
                SymbolKind.RECORD, SymbolKind.ANNOTATION,
            ) else parent_fqn
            for child in node.children:
                self._extract_nodes(child, parent_fqn=new_parent)
        else:
            # Recurse without creating a symbol
            for child in node.children:
                self._extract_nodes(child, parent_fqn=parent_fqn)

    def _extract_field_nodes(self, node, parent_fqn: Optional[str]):
        """Extract field declarations — a single ``field_declaration``
        can declare multiple variables."""
        modifiers = self._collect_modifiers(node)
        annotations = self._collect_annotations(node)
        field_type = self._get_field_type(node)

        containing = self._find_containing_type_names(node)

        for child in node.children:
            if child.type == "variable_declarator":
                ident = self._get_identifier(child)
                if not ident:
                    continue
                field_name = ident.text.decode()
                name = f"{containing[-1]}.{field_name}" if containing else field_name
                fqn = self._qualify_name(
                    ".".join([*containing, field_name])
                )

                symbol = ASTSymbolNode(
                    symbol_id=fqn,
                    language=Language.JAVA,
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
                    docstring=self._extract_javadoc(node),
                    parent_symbol_id=(
                        self._qualify_name(".".join(containing))
                        if containing else parent_fqn
                    ),
                    field_type=field_type,
                )
                self.symbols.append(symbol)
                self._symbol_lookup[fqn] = symbol

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
        annotations = self._collect_annotations(node)
        docstring = self._extract_javadoc(node)

        # Method / constructor signature
        signature: Optional[MethodSignature] = None
        if kind in (SymbolKind.METHOD, SymbolKind.CONSTRUCTOR):
            signature = self._build_method_signature(node, kind)

        # Inheritance
        extends = None
        implements_list: List[str] = []
        if kind in (SymbolKind.CLASS, SymbolKind.RECORD):
            extends = self._extract_extends(node)
            implements_list = self._extract_implements(node)
        elif kind == SymbolKind.INTERFACE:
            # Interfaces "extend" other interfaces
            implements_list = self._extract_interface_extends(node)
        elif kind == SymbolKind.ENUM:
            implements_list = self._extract_implements(node)

        return ASTSymbolNode(
            symbol_id=fqn,
            language=Language.JAVA,
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
        "public", "private", "protected", "static", "final", "abstract",
        "synchronized", "native", "strictfp", "transient", "volatile",
        "default", "sealed", "non-sealed",
    }

    def _collect_modifiers(self, node) -> List[str]:
        mods = []
        for child in node.children:
            if child.type == "modifiers":
                for mod_child in child.children:
                    text = mod_child.text.decode()
                    if text in self._MODIFIER_KEYWORDS:
                        mods.append(text)
        return mods

    @staticmethod
    def _has_modifier(node, modifier: str) -> bool:
        for child in node.children:
            if child.type == "modifiers":
                for mod_child in child.children:
                    if mod_child.text.decode() == modifier:
                        return True
        return False

    # ------------------------------------------------------------------
    # Annotations
    # ------------------------------------------------------------------

    def _collect_annotations(self, node) -> List[AnnotationInfo]:
        annotations = []
        for child in node.children:
            if child.type == "modifiers":
                for mod_child in child.children:
                    if mod_child.type in ("marker_annotation", "annotation"):
                        annotations.append(self._parse_annotation(mod_child))
        return annotations

    @staticmethod
    def _parse_annotation(ann_node) -> AnnotationInfo:
        name = ""
        args: Dict[str, str] = {}

        name_node = next(
            (c for c in ann_node.children if c.type in ("identifier", "scoped_identifier")),
            None,
        )
        if name_node:
            name = name_node.text.decode()

        # Parse annotation arguments
        arg_list = next(
            (c for c in ann_node.children if c.type == "annotation_argument_list"),
            None,
        )
        if arg_list:
            for arg_child in arg_list.children:
                if arg_child.type == "element_value_pair":
                    key_node = next(
                        (c for c in arg_child.children if c.type == "identifier"),
                        None,
                    )
                    # Value is everything after the '='
                    val_nodes = [
                        c for c in arg_child.children
                        if c.type not in ("identifier", "=")
                    ]
                    if key_node and val_nodes:
                        args[key_node.text.decode()] = val_nodes[0].text.decode().strip('"')
                elif arg_child.type not in ("(", ")", ","):
                    # Single-value annotation like @SuppressWarnings("unchecked")
                    args["value"] = arg_child.text.decode().strip('"')

        return AnnotationInfo(name=name, arguments=args)

    # ------------------------------------------------------------------
    # Javadoc extraction
    # ------------------------------------------------------------------

    def _extract_javadoc(self, node) -> Optional[str]:
        """Extract the Javadoc comment immediately preceding a declaration."""
        sib = node.prev_sibling
        # Skip attribute lists between comment and declaration
        while sib is not None and sib.type in ("modifiers",):
            sib = sib.prev_sibling

        # Also check inside the node's children for a leading block_comment
        if sib is None:
            # Try looking at previous sibling before the modifiers
            # (modifiers might absorb the javadoc as a sibling)
            pass

        # Actually, in tree-sitter-java, Javadoc is a block_comment sibling
        # before the declaration or before its modifiers.
        sib = node.prev_sibling
        while sib is not None:
            if sib.type == "line_comment":
                sib = sib.prev_sibling
                continue
            if sib.type == "block_comment":
                text = sib.text.decode()
                if text.startswith("/**"):
                    return BaseLanguageParser._clean_javadoc(text)
            break

        return None

    # ------------------------------------------------------------------
    # Method / constructor signature
    # ------------------------------------------------------------------

    def _build_method_signature(self, node, kind: SymbolKind) -> MethodSignature:
        return_type = None
        params: List[ParameterInfo] = []
        thrown: List[str] = []
        is_async = False  # Not applicable in Java

        # Return type (for methods)
        if kind == SymbolKind.METHOD:
            for child in node.children:
                if child.type in (
                    "type_identifier", "generic_type", "void_type",
                    "integral_type", "floating_point_type", "boolean_type",
                    "array_type", "scoped_type_identifier",
                ):
                    return_type = child.text.decode()
                    break

        # Parameters
        param_list = next(
            (c for c in node.children if c.type == "formal_parameters"),
            None,
        )
        if param_list:
            for param in param_list.children:
                if param.type in ("formal_parameter", "spread_parameter"):
                    p_type_node = next(
                        (c for c in param.children if c.type in (
                            "type_identifier", "generic_type", "integral_type",
                            "floating_point_type", "boolean_type", "void_type",
                            "array_type", "scoped_type_identifier",
                        )),
                        None,
                    )
                    p_name_node = next(
                        (c for c in param.children if c.type == "identifier"),
                        None,
                    )
                    if p_name_node:
                        p_mods = []
                        if param.type == "spread_parameter":
                            p_mods.append("varargs")
                        params.append(ParameterInfo(
                            name=p_name_node.text.decode(),
                            type=p_type_node.text.decode() if p_type_node else "unknown",
                            modifiers=p_mods,
                        ))

        # Throws clause
        throws_node = next(
            (c for c in node.children if c.type == "throws"),
            None,
        )
        if throws_node:
            for tc in throws_node.children:
                if tc.type in ("type_identifier", "scoped_type_identifier"):
                    thrown.append(tc.text.decode())

        return MethodSignature(
            return_type=return_type,
            parameters=params,
            thrown_exceptions=thrown,
            is_async=is_async,
        )

    # ------------------------------------------------------------------
    # Inheritance
    # ------------------------------------------------------------------

    def _extract_extends(self, node) -> Optional[str]:
        sc = next((c for c in node.children if c.type == "superclass"), None)
        if sc:
            type_name = self._get_type_name(sc)
            if type_name:
                return self._resolve_type(type_name)
        return None

    def _extract_implements(self, node) -> List[str]:
        result = []
        impl_node = next(
            (c for c in node.children if c.type == "super_interfaces"),
            None,
        )
        if impl_node:
            for child in impl_node.children:
                if child.type == "type_list":
                    for tc in child.children:
                        if tc.type in ("type_identifier", "generic_type"):
                            name = self._get_type_name(tc)
                            if name:
                                result.append(self._resolve_type(name))
        return result

    def _extract_interface_extends(self, node) -> List[str]:
        result = []
        ext_node = next(
            (c for c in node.children if c.type == "extends_interfaces"),
            None,
        )
        if ext_node:
            for child in ext_node.children:
                if child.type == "type_list":
                    for tc in child.children:
                        if tc.type in ("type_identifier", "generic_type"):
                            name = self._get_type_name(tc)
                            if name:
                                result.append(self._resolve_type(name))
        return result

    # ------------------------------------------------------------------
    # Relationship extraction (call graph)
    # ------------------------------------------------------------------

    def _extract_relationships(self, node):
        # Inheritance edges
        if node.type in self._TYPE_DECLARATIONS:
            type_name = self._get_identifier_text(node)
            if type_name:
                fqn = self._fqn_for_type_at(node, type_name)
                extends = self._extract_extends(node)
                if extends and not self._is_external(extends):
                    self.relationships.append(RelationshipEdge(
                        source=fqn, target=extends, kind="extends",
                        line=node.start_point[0] + 1,
                    ))
                for iface in self._extract_implements(node):
                    if not self._is_external(iface):
                        self.relationships.append(RelationshipEdge(
                            source=fqn, target=iface, kind="implements",
                            line=node.start_point[0] + 1,
                        ))

        # Method invocations
        if node.type == "method_invocation":
            self._handle_method_invocation(node)

        # Object creation
        if node.type == "object_creation_expression":
            self._handle_object_creation(node)

        for child in node.children:
            self._extract_relationships(child)

    def _handle_method_invocation(self, node):
        caller_fqn = self._find_enclosing_method_fqn(node) or self._find_enclosing_type_fqn(node)
        if not caller_fqn:
            return

        identifiers = [c.text.decode() for c in node.children if c.type == "identifier"]
        if len(identifiers) >= 2:
            receiver, method = identifiers[0], identifiers[1]
            target_type = self._resolve_type(receiver) if receiver[0:1].isupper() else None
            if target_type and not self._is_external(target_type):
                callee = f"{target_type}.{method}"
                self.relationships.append(RelationshipEdge(
                    source=caller_fqn, target=callee, kind="calls",
                    line=node.start_point[0] + 1,
                ))
        elif len(identifiers) == 1:
            method = identifiers[0]
            containing_type = self._find_enclosing_type_fqn(node)
            if containing_type:
                callee = f"{containing_type}.{method}"
                self.relationships.append(RelationshipEdge(
                    source=caller_fqn, target=callee, kind="calls",
                    line=node.start_point[0] + 1,
                ))

    def _handle_object_creation(self, node):
        caller_fqn = self._find_enclosing_type_fqn(node)
        if not caller_fqn:
            return
        type_node = next(
            (c for c in node.children if c.type in ("type_identifier", "generic_type")),
            None,
        )
        if type_node:
            created = self._get_type_name(type_node)
            if created:
                resolved = self._resolve_type(created)
                if not self._is_external(resolved):
                    self.relationships.append(RelationshipEdge(
                        source=caller_fqn, target=resolved, kind="instantiates",
                        line=node.start_point[0] + 1,
                    ))

    # ------------------------------------------------------------------
    # Field type extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _get_field_type(node) -> Optional[str]:
        for child in node.children:
            if child.type in (
                "type_identifier", "generic_type", "integral_type",
                "floating_point_type", "boolean_type", "void_type",
                "array_type", "scoped_type_identifier",
            ):
                return child.text.decode()
        return None

    # ------------------------------------------------------------------
    # Name resolution helpers
    # ------------------------------------------------------------------

    def _qualify_name(self, name: str) -> str:
        if self.package_name:
            return f"{self.package_name}.{name}"
        return name

    def _resolve_type(self, type_name: str) -> str:
        simple = type_name.split("<", 1)[0].strip()
        if "." in simple:
            return simple
        if simple in self.import_map:
            return self.import_map[simple]
        if self.package_name:
            return f"{self.package_name}.{simple}"
        return simple

    @staticmethod
    def _is_external(fqn: str) -> bool:
        simple = fqn.split(".")[-1] if "." in fqn else fqn
        if simple in _JAVA_PRIMITIVES:
            return True
        for prefix in _JAVA_EXTERNAL_PREFIXES:
            if fqn.startswith(prefix):
                return True
        return False

    def _fqn_for_type_at(self, node, type_name: str) -> str:
        containing = self._find_containing_type_names(node)
        return self._qualify_name(".".join([*containing, type_name]))

    def _find_enclosing_type_fqn(self, node) -> Optional[str]:
        names = self._find_containing_type_names(node)
        if names:
            return self._qualify_name(".".join(names))
        return None

    def _find_enclosing_method_fqn(self, node) -> Optional[str]:
        current = node.parent
        while current:
            if current.type == "method_declaration":
                method_name = self._get_identifier_text(current)
                containing = self._find_containing_type_names(current)
                if method_name and containing:
                    return self._qualify_name(".".join([*containing, method_name]))
            current = current.parent
        return None

    # ------------------------------------------------------------------
    # Tree-sitter helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_containing_type_names(node) -> List[str]:
        names = []
        current = node.parent
        while current:
            if current.type in (
                "class_declaration", "interface_declaration",
                "enum_declaration", "record_declaration",
                "annotation_type_declaration",
            ):
                name_node = next(
                    (c for c in current.children if c.type == "identifier"),
                    None,
                )
                if name_node:
                    names.append(name_node.text.decode())
            current = current.parent
        return list(reversed(names))

    @staticmethod
    def _get_identifier(node):
        return next(
            (c for c in node.children if c.type == "identifier"),
            None,
        )

    @staticmethod
    def _get_identifier_text(node) -> Optional[str]:
        ident = next(
            (c for c in node.children if c.type == "identifier"),
            None,
        )
        return ident.text.decode() if ident else None

    @staticmethod
    def _get_type_name(node) -> Optional[str]:
        if node.type == "type_identifier":
            return node.text.decode()
        if node.type == "generic_type":
            t = next(
                (c for c in node.children if c.type == "type_identifier"),
                None,
            )
            return t.text.decode() if t else None
        if node.type == "superclass":
            t = next(
                (c for c in node.children if c.type in ("type_identifier", "generic_type")),
                None,
            )
            if t:
                return t.text.decode() if t.type == "type_identifier" else (
                    next(
                        (c for c in t.children if c.type == "type_identifier"),
                        None,
                    ).text.decode()
                    if any(c.type == "type_identifier" for c in t.children) else None
                )
        return None

    @staticmethod
    def _find_child_by_types(node, types: tuple):
        return next(
            (c for c in node.children if c.type in types),
            None,
        )
