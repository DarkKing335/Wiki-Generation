"""Pydantic contracts for RepoAtlas's persistent knowledge graph."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class GraphRange(BaseModel):
    start_line: int
    end_line: int


class GraphMetadata(BaseModel):
    """Display and analysis metadata carried by a graph node."""

    modifiers: List[str] = Field(default_factory=list)
    annotations: List[Dict[str, Any]] = Field(default_factory=list)
    docstring: Optional[str] = None
    signature: Optional[Dict[str, Any]] = None
    property_accessors: Optional[Dict[str, Any]] = None
    field_type: Optional[str] = None
    fully_qualified_name: Optional[str] = None
    parent_symbol_id: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    extends: Optional[str] = None
    implements: List[str] = Field(default_factory=list)
    package_or_namespace: Optional[str] = None
    imports: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None
    generated_by: Optional[str] = None
    referenced_symbols: List[str] = Field(default_factory=list)
    derived_by: Optional[str] = None
    marker_file: Optional[str] = None
    external: bool = False


class GraphNode(BaseModel):
    id: str
    type: str
    name: str
    language: Optional[str] = None
    file_path: Optional[str] = None
    range: Optional[GraphRange] = None
    metadata: GraphMetadata = Field(default_factory=GraphMetadata)


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str
    line: Optional[int] = None
    origin: str = Field(
        default="index",
        description="Producer of the edge: index, taxonomy, or graph_builder",
    )


class RepositoryMetadata(BaseModel):
    name: str
    path: str
    languages: List[str] = Field(default_factory=list)


class GraphContentSection(BaseModel):
    key: str
    title: str
    body: str
    facts: Dict[str, List[str]] = Field(default_factory=dict)
    generated_by: str = "structural"


class KnowledgeGraph(BaseModel):
    """Self-contained Epic 2 artefact written to ``graphs/graph.json``."""

    schema_version: str = "1.0"
    repository: RepositoryMetadata
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    content: List[GraphContentSection] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_graph_integrity(self) -> "KnowledgeGraph":
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Graph node IDs must be unique")
        known = set(node_ids)
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError(
                    f"Edge endpoint is missing: {edge.source} -> {edge.target}"
                )
        return self


class QueryResult(BaseModel):
    node: GraphNode
    direction: str
    edges: List[GraphEdge] = Field(default_factory=list)
    related_nodes: List[GraphNode] = Field(default_factory=list)


class PathResult(BaseModel):
    source: str
    target: str
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.nodes)
