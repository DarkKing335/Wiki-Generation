"""In-memory relationship queries for ``graph.json``."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import DefaultDict, Iterable, Optional

from knowledge_graph.models import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    PathResult,
    QueryResult,
)


DEPENDENCY_KINDS = frozenset({"extends", "implements", "calls", "uses_field", "instantiates"})


class GraphQuery:
    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        self.nodes = {node.id: node for node in graph.nodes}
        self._outgoing: DefaultDict[str, list[GraphEdge]] = defaultdict(list)
        self._incoming: DefaultDict[str, list[GraphEdge]] = defaultdict(list)
        for edge in graph.edges:
            self._outgoing[edge.source].append(edge)
            self._incoming[edge.target].append(edge)

    def get_node(self, node_id: str) -> GraphNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:
            raise KeyError(f"Unknown graph node: '{node_id}'") from exc

    @staticmethod
    def _filter(edges: Iterable[GraphEdge], kinds: Optional[Iterable[str]]) -> list[GraphEdge]:
        selected = set(kinds) if kinds else None
        return [edge for edge in edges if selected is None or edge.kind in selected]

    def outgoing(self, node_id: str, kinds: Optional[Iterable[str]] = None) -> list[GraphEdge]:
        self.get_node(node_id)
        return self._filter(self._outgoing[node_id], kinds)

    def incoming(self, node_id: str, kinds: Optional[Iterable[str]] = None) -> list[GraphEdge]:
        self.get_node(node_id)
        return self._filter(self._incoming[node_id], kinds)

    def query(
        self,
        node_id: str,
        direction: str = "both",
        kinds: Optional[Iterable[str]] = None,
    ) -> QueryResult:
        node = self.get_node(node_id)
        if direction == "outgoing":
            edges = self.outgoing(node_id, kinds)
            related_ids = [edge.target for edge in edges]
        elif direction == "incoming":
            edges = self.incoming(node_id, kinds)
            related_ids = [edge.source for edge in edges]
        elif direction == "both":
            outgoing = self.outgoing(node_id, kinds)
            incoming = self.incoming(node_id, kinds)
            edges = outgoing + incoming
            related_ids = [edge.target for edge in outgoing] + [edge.source for edge in incoming]
        else:
            raise ValueError("direction must be outgoing, incoming, or both")

        seen: set[str] = set()
        related_nodes = []
        for related_id in related_ids:
            if related_id not in seen:
                seen.add(related_id)
                related_nodes.append(self.get_node(related_id))
        return QueryResult(node=node, direction=direction, edges=edges, related_nodes=related_nodes)

    def dependencies(
        self,
        node_id: str,
        kinds: Optional[Iterable[str]] = None,
    ) -> QueryResult:
        selected = DEPENDENCY_KINDS if kinds is None else kinds
        return self.query(node_id, "outgoing", selected)

    def dependents(
        self,
        node_id: str,
        kinds: Optional[Iterable[str]] = None,
    ) -> QueryResult:
        selected = DEPENDENCY_KINDS if kinds is None else kinds
        return self.query(node_id, "incoming", selected)

    def shortest_path(
        self,
        source: str,
        target: str,
        kinds: Optional[Iterable[str]] = None,
    ) -> PathResult:
        self.get_node(source)
        self.get_node(target)
        if source == target:
            return PathResult(source=source, target=target, nodes=[self.nodes[source]])

        allowed = set(kinds) if kinds else None
        queue = deque([source])
        previous: dict[str, tuple[str, GraphEdge]] = {}
        visited = {source}

        while queue:
            current = queue.popleft()
            for edge in self._outgoing[current]:
                if allowed is not None and edge.kind not in allowed:
                    continue
                if edge.target in visited:
                    continue
                visited.add(edge.target)
                previous[edge.target] = (current, edge)
                if edge.target == target:
                    return self._reconstruct_path(source, target, previous)
                queue.append(edge.target)

        return PathResult(source=source, target=target)

    def _reconstruct_path(
        self,
        source: str,
        target: str,
        previous: dict[str, tuple[str, GraphEdge]],
    ) -> PathResult:
        node_ids = [target]
        edges: list[GraphEdge] = []
        current = target
        while current != source:
            parent, edge = previous[current]
            node_ids.append(parent)
            edges.append(edge)
            current = parent
        node_ids.reverse()
        edges.reverse()
        return PathResult(
            source=source,
            target=target,
            nodes=[self.nodes[node_id] for node_id in node_ids],
            edges=edges,
        )
