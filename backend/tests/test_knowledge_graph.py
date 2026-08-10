"""Epic 2 knowledge graph generation, persistence, queries, and CLI tests."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ai_analysis.ir_models import RelationshipEdge
from ai_analysis.models import AnalysisResult, ContentSection, SummaryNode, Tier
from knowledge_graph.__main__ import build_parser, main, run
from knowledge_graph.builder import GraphBuilder, build_from_paths, load_graph, write_graph
from knowledge_graph.models import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    RepositoryMetadata,
)
from knowledge_graph.query import GraphQuery


def test_builds_self_contained_graph(sample_index, stub_overview):
    graph = GraphBuilder(sample_index, overview=stub_overview).build()

    assert graph.schema_version == "1.0"
    assert graph.repository.name == "sample_repo"
    assert set(graph.repository.languages) == {"java", "csharp"}
    assert any(node.type == "REPOSITORY" for node in graph.nodes)
    assert any(node.type == "MODULE" for node in graph.nodes)
    assert any(node.type == "FILE" for node in graph.nodes)
    assert any(node.type == "CLASS" for node in graph.nodes)

    renderer = next(node for node in graph.nodes if node.id.endswith("InvoiceRenderer"))
    assert renderer.metadata.docstring == "Renders invoices to PDF for delivery to customers."
    assert renderer.metadata.fully_qualified_name == renderer.id
    assert renderer.file_path.endswith("InvoiceRenderer.java")

    node_ids = {node.id for node in graph.nodes}
    assert all(edge.source in node_ids and edge.target in node_ids for edge in graph.edges)


def test_unresolved_relationship_targets_become_external_nodes(sample_index):
    graph = GraphBuilder(sample_index).build()
    external = {node.id: node for node in graph.nodes if node.type == "EXTERNAL"}

    assert "TemplateEngine" in external
    assert external["TemplateEngine"].metadata.external is True


def test_preserves_and_queries_call_edges(sample_index):
    index = sample_index.model_copy(deep=True)
    source = index.symbols[0].symbol_id
    target = index.symbols[3].symbol_id
    index.relationships.append(
        RelationshipEdge(source=source, target=target, kind="calls", line=24)
    )

    graph = GraphBuilder(index).build()
    query = GraphQuery(graph)
    dependencies = query.dependencies(source)
    dependents = query.dependents(target)

    assert any(edge.kind == "calls" and edge.target == target for edge in dependencies.edges)
    assert any(node.id == source for node in dependents.related_nodes)


def test_analysis_enriches_taxonomy_nodes_and_content(sample_index, sample_tree):
    root = sample_tree.root
    analysis = AnalysisResult(
        repository_name=sample_index.repository_name,
        repository_path=sample_index.repository_path,
        taxonomy=sample_tree,
        summaries=[
            SummaryNode(
                node_id=root.node_id,
                tier=Tier.REPOSITORY,
                name=root.name,
                summary="Repository-level summary.",
                generated_by="structural",
            )
        ],
        content=[
            ContentSection(
                key="architecture",
                title="Architecture",
                body="Layered services.",
            )
        ],
    )

    graph = GraphBuilder(sample_index, analysis=analysis).build()
    repository = next(node for node in graph.nodes if node.type == "REPOSITORY")

    assert repository.metadata.summary == "Repository-level summary."
    assert graph.content[0].key == "architecture"
    assert any(node.type == "COMPONENT" for node in graph.nodes)


def test_rejects_analysis_for_another_repository(sample_index, sample_tree):
    analysis = AnalysisResult(
        repository_name="different",
        repository_path=sample_index.repository_path,
        taxonomy=sample_tree,
    )
    with pytest.raises(ValueError, match="does not match"):
        GraphBuilder(sample_index, analysis=analysis)


def test_graph_schema_rejects_dangling_edges():
    with pytest.raises(ValidationError, match="Edge endpoint is missing"):
        KnowledgeGraph(
            repository=RepositoryMetadata(name="repo", path="/repo"),
            nodes=[GraphNode(id="a", type="CLASS", name="A")],
            edges=[GraphEdge(source="a", target="missing", kind="calls")],
        )


@pytest.fixture
def query_graph():
    return KnowledgeGraph(
        repository=RepositoryMetadata(name="repo", path="/repo"),
        nodes=[GraphNode(id=node_id, type="CLASS", name=node_id.upper()) for node_id in "abcd"],
        edges=[
            GraphEdge(source="a", target="b", kind="calls"),
            GraphEdge(source="b", target="c", kind="calls"),
            GraphEdge(source="a", target="d", kind="contains"),
            GraphEdge(source="c", target="a", kind="calls"),
        ],
    )


def test_query_directions_filters_and_cycles(query_graph):
    query = GraphQuery(query_graph)

    assert [edge.target for edge in query.outgoing("a", ["calls"])] == ["b"]
    assert [edge.source for edge in query.incoming("a", ["calls"])] == ["c"]
    assert {node.id for node in query.query("a", "both").related_nodes} == {"b", "c", "d"}

    path = query.shortest_path("a", "c", ["calls"])
    assert [node.id for node in path.nodes] == ["a", "b", "c"]
    assert not query.shortest_path("d", "c").found

    with pytest.raises(KeyError, match="Unknown graph node"):
        query.get_node("missing")


def test_write_is_deterministic_and_replaces_previous_graph(tmp_path, query_graph):
    path = write_graph(query_graph, tmp_path)
    first = path.read_bytes()
    assert write_graph(query_graph, tmp_path).read_bytes() == first

    smaller = KnowledgeGraph(
        repository=query_graph.repository,
        nodes=[GraphNode(id="only", type="CLASS", name="Only")],
    )
    write_graph(smaller, tmp_path)
    loaded = load_graph(tmp_path)
    assert [node.id for node in loaded.nodes] == ["only"]


def test_path_loaders_and_cli(sample_index_dir, tmp_path, capsys):
    graph = build_from_paths(sample_index_dir)
    assert graph.repository.name == "sample_repo"

    parser = build_parser()
    output_dir = tmp_path / "graphs"
    assert run(parser.parse_args([
        "build", str(sample_index_dir), "-o", str(output_dir)
    ])) == 0
    assert (output_dir / "graph.json").exists()

    repository_id = "repository:sample_repo"
    assert run(parser.parse_args([
        "query", str(output_dir), repository_id, "--direction", "outgoing"
    ])) == 0
    output = capsys.readouterr().out
    assert '"direction": "outgoing"' in output

    symbol_id = "com.acme.billing.payment.PaymentProcessor"
    for command in ("dependencies", "dependents"):
        assert run(parser.parse_args([command, str(output_dir), symbol_id])) == 0

    target_id = "com.acme.billing.payment.PaymentGateway"
    assert run(parser.parse_args([
        "path", str(output_dir), symbol_id, target_id, "--kind", "implements"
    ])) == 0
    assert '"target": "com.acme.billing.payment.PaymentGateway"' in capsys.readouterr().out


def test_cli_error_exit_codes(tmp_path, query_graph, capsys):
    graph_dir = tmp_path / "graphs"
    write_graph(query_graph, graph_dir)

    with pytest.raises(SystemExit) as missing_input:
        main(["build", str(tmp_path / "missing")])
    assert missing_input.value.code == 1
    assert "repository_index.json not found" in capsys.readouterr().err

    with pytest.raises(SystemExit) as unknown_node:
        main(["query", str(graph_dir), "missing"])
    assert unknown_node.value.code == 2
    assert "Unknown graph node" in capsys.readouterr().err
