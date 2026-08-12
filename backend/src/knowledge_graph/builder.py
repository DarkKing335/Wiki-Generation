"""Build and persist the Epic 2 knowledge graph."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Optional

from ai_analysis.ir_models import StructureOverview
from ai_analysis.models import AnalysisResult, TaxonomyNode, Tier
from core_indexing.models import ASTSymbolNode, RepositoryIndex

from knowledge_graph.models import (
    GraphContentSection,
    GraphEdge,
    GraphMetadata,
    GraphNode,
    KnowledgeGraph,
    RepositoryMetadata,
)


def _read_json(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _resolve_input(path: str | Path, filename: str) -> Path:
    resolved = Path(path)
    if resolved.is_dir():
        resolved = resolved / filename
    if not resolved.exists():
        raise FileNotFoundError(f"{filename} not found at '{resolved}'")
    return resolved


def load_repository_index(path: str | Path) -> RepositoryIndex:
    return RepositoryIndex.model_validate_json(
        _read_json(_resolve_input(path, "repository_index.json"))
    )


def load_structure_overview(path: str | Path) -> Optional[StructureOverview]:
    candidate = Path(path)
    if candidate.is_file():
        candidate = candidate.parent
    candidate = candidate / "structure_overview.json"
    if not candidate.exists():
        return None
    return StructureOverview.model_validate_json(_read_json(candidate))


def load_analysis(path: str | Path) -> AnalysisResult:
    return AnalysisResult.model_validate_json(
        _read_json(_resolve_input(path, "summaries.json"))
    )


def load_graph(path: str | Path) -> KnowledgeGraph:
    return KnowledgeGraph.model_validate_json(_read_json(_resolve_input(path, "graph.json")))


class GraphBuilder:
    """Convert Epic 1 IR, optionally enriched by Epic 3, into a graph."""

    def __init__(
        self,
        index: RepositoryIndex,
        overview: Optional[StructureOverview] = None,
        analysis: Optional[AnalysisResult] = None,
    ):
        if analysis and analysis.repository_name != index.repository_name:
            raise ValueError(
                "Analysis repository does not match index: "
                f"'{analysis.repository_name}' != '{index.repository_name}'"
            )
        if analysis and analysis.repository_path != index.repository_path:
            raise ValueError("Analysis repository_path does not match repository index")

        self.index = index
        self.overview = overview
        self.analysis = analysis
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._taxonomy_ids: Dict[str, str] = {}

    @property
    def repository_id(self) -> str:
        return f"repository:{self.index.repository_name}"

    def build(self) -> KnowledgeGraph:
        self._add_repository()
        self._add_files_and_symbols()
        self._add_index_relationships()

        if self.analysis:
            self._add_analysis_taxonomy(self.analysis.taxonomy.root)
            self._attach_summaries()
        elif self.overview:
            self._add_overview_taxonomy()

        nodes = sorted(self._nodes.values(), key=lambda node: node.id)
        edges = sorted(
            self._edges,
            key=lambda edge: (
                edge.source,
                edge.target,
                edge.kind,
                edge.line if edge.line is not None else -1,
                edge.origin,
            ),
        )
        content = []
        if self.analysis:
            content = [
                GraphContentSection.model_validate(section.model_dump(mode="json"))
                for section in self.analysis.content
            ]
            content.sort(key=lambda section: section.key)

        return KnowledgeGraph(
            repository=RepositoryMetadata(
                name=self.index.repository_name,
                path=self.index.repository_path,
                languages=sorted(language.value for language in self.index.languages),
            ),
            nodes=nodes,
            edges=edges,
            content=content,
        )

    def _add_repository(self) -> None:
        self._nodes[self.repository_id] = GraphNode(
            id=self.repository_id,
            type="REPOSITORY",
            name=self.index.repository_name,
        )

    def _add_files_and_symbols(self) -> None:
        for file_index in self.index.files:
            file_id = f"file:{file_index.file_path}"
            self._nodes[file_id] = GraphNode(
                id=file_id,
                type="FILE",
                name=Path(file_index.file_path).name,
                language=file_index.language.value,
                file_path=file_index.file_path,
                metadata=GraphMetadata(
                    package_or_namespace=file_index.package_or_namespace,
                    imports=[item.model_dump(mode="json", exclude_none=True) for item in file_index.imports],
                ),
            )
            self._add_generated_edge(self.repository_id, file_id, "contains")

        for symbol in self.index.symbols:
            self._nodes[symbol.symbol_id] = self._symbol_node(symbol)
            file_id = f"file:{symbol.file_path}"
            if file_id not in self._nodes:
                self._nodes[file_id] = GraphNode(
                    id=file_id,
                    type="FILE",
                    name=Path(symbol.file_path).name,
                    language=symbol.language.value,
                    file_path=symbol.file_path,
                )
                self._add_generated_edge(self.repository_id, file_id, "contains")
            self._add_generated_edge(file_id, symbol.symbol_id, "declares")

    @staticmethod
    def _symbol_node(symbol: ASTSymbolNode) -> GraphNode:
        return GraphNode(
            id=symbol.symbol_id,
            type=symbol.kind.value,
            name=symbol.name,
            language=symbol.language.value,
            file_path=symbol.file_path,
            range=symbol.range.model_dump(mode="json"),
            metadata=GraphMetadata(
                modifiers=list(symbol.modifiers),
                annotations=[item.model_dump(mode="json") for item in symbol.annotations],
                docstring=symbol.docstring,
                signature=(symbol.signature.model_dump(mode="json") if symbol.signature else None),
                property_accessors=(
                    symbol.property_accessors.model_dump(mode="json")
                    if symbol.property_accessors else None
                ),
                field_type=symbol.field_type,
                fully_qualified_name=symbol.fully_qualified_name,
                parent_symbol_id=symbol.parent_symbol_id,
                dependencies=list(symbol.dependencies),
                extends=symbol.extends,
                implements=list(symbol.implements),
            ),
        )

    def _add_index_relationships(self) -> None:
        for relationship in self.index.relationships:
            self._ensure_endpoint(relationship.source)
            self._ensure_endpoint(relationship.target)
            self._edges.append(GraphEdge(
                source=relationship.source,
                target=relationship.target,
                kind=relationship.kind,
                line=relationship.line,
                origin="index",
            ))

    def _ensure_endpoint(self, node_id: str) -> None:
        if node_id in self._nodes:
            return
        self._nodes[node_id] = GraphNode(
            id=node_id,
            type="EXTERNAL",
            name=node_id.rsplit(".", 1)[-1],
            metadata=GraphMetadata(external=True),
        )

    def _add_analysis_taxonomy(
        self,
        node: TaxonomyNode,
        parent_graph_id: Optional[str] = None,
    ) -> None:
        graph_id = self._graph_id_for_taxonomy(node)
        self._taxonomy_ids[node.node_id] = graph_id

        if graph_id not in self._nodes:
            self._nodes[graph_id] = GraphNode(
                id=graph_id,
                type=node.tier.name,
                name=node.name,
                language=node.language.value if node.language else None,
                file_path=node.path,
                metadata=GraphMetadata(
                    derived_by=node.derived_by,
                    marker_file=node.marker_file,
                ),
            )
        else:
            self._nodes[graph_id].metadata.derived_by = node.derived_by
            self._nodes[graph_id].metadata.marker_file = node.marker_file

        if parent_graph_id and parent_graph_id != graph_id:
            self._add_generated_edge(parent_graph_id, graph_id, "contains", origin="taxonomy")

        for child in node.children:
            self._add_analysis_taxonomy(child, graph_id)

    def _graph_id_for_taxonomy(self, node: TaxonomyNode) -> str:
        if node.tier is Tier.REPOSITORY:
            return self.repository_id
        if node.symbol_id and node.symbol_id in self._nodes:
            return node.symbol_id
        return f"taxonomy:{node.node_id}"

    def _attach_summaries(self) -> None:
        assert self.analysis is not None
        for summary in self.analysis.summaries:
            graph_id = self._taxonomy_ids.get(summary.node_id, summary.node_id)
            if graph_id not in self._nodes:
                graph_id = f"taxonomy:{summary.node_id}"
                self._nodes[graph_id] = GraphNode(
                    id=graph_id,
                    type=summary.tier.name,
                    name=summary.name,
                )
                self._add_generated_edge(self.repository_id, graph_id, "contains", origin="taxonomy")
            metadata = self._nodes[graph_id].metadata
            metadata.summary = summary.summary
            metadata.generated_by = summary.generated_by
            metadata.referenced_symbols = list(summary.referenced_symbols)

    def _add_overview_taxonomy(self) -> None:
        assert self.overview is not None
        for module in self.overview.modules:
            module_name = str(module.get("name", "module"))
            module_id = f"taxonomy:module:{module_name}"
            self._add_group_node(module_id, "MODULE", module_name, self.repository_id)
            for container in module.get("containers", []):
                container_name = str(container.get("name", "container"))
                container_id = f"taxonomy:container:{module_name}:{container_name}"
                self._add_group_node(container_id, "CONTAINER", container_name, module_id)
                for component in container.get("components", []):
                    component_name = str(component.get("name", "component"))
                    component_id = (
                        f"taxonomy:component:{module_name}:{container_name}:{component_name}"
                    )
                    self._add_group_node(component_id, "COMPONENT", component_name, container_id)
                    for class_info in component.get("classes", []):
                        symbol_id = class_info.get("fqn")
                        if symbol_id in self._nodes:
                            self._add_generated_edge(
                                component_id, symbol_id, "contains", origin="taxonomy"
                            )

    def _add_group_node(
        self,
        node_id: str,
        node_type: str,
        name: str,
        parent_id: str,
    ) -> None:
        self._nodes.setdefault(
            node_id,
            GraphNode(id=node_id, type=node_type, name=name),
        )
        self._add_generated_edge(parent_id, node_id, "contains", origin="taxonomy")

    def _add_generated_edge(
        self,
        source: str,
        target: str,
        kind: str,
        origin: str = "graph_builder",
    ) -> None:
        if any(
            edge.source == source and edge.target == target and edge.kind == kind
            for edge in self._edges
        ):
            return
        self._edges.append(GraphEdge(source=source, target=target, kind=kind, origin=origin))


def build_from_paths(
    index_path: str | Path,
    analysis_path: Optional[str | Path] = None,
) -> KnowledgeGraph:
    index = load_repository_index(index_path)
    overview = load_structure_overview(index_path)
    analysis = load_analysis(analysis_path) if analysis_path else None
    return GraphBuilder(index=index, overview=overview, analysis=analysis).build()


def write_graph(graph: KnowledgeGraph, output_dir: str | Path = "graphs") -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    output_file = output / "graph.json"
    payload = json.dumps(
        graph.model_dump(mode="json", exclude_none=True),
        indent=2,
        sort_keys=False,
    ) + "\n"

    temporary_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output,
            prefix=".graph.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary_name = temporary.name
        os.replace(temporary_name, output_file)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return output_file
