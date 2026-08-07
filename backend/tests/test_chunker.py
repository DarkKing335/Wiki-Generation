"""Chunker tests — the AST-boundary guarantee (FR-13, ``docs/epics.md`` Epic 3).

Epic 3's headline claim is *zero context boundary cuts*: a chunk is always
exactly one AST node, never a slice of lines.  These tests assert that
property directly, and assert the lazy source-loading contract from
``docs/designs/ast-parser-design.md`` §8 — that raw source arrives only on
explicit request, and only for the exact range the AST recorded.
"""

from __future__ import annotations

import pytest

from ai_analysis.chunker import Chunk, Chunker
from ai_analysis.models import Tier


@pytest.fixture
def chunker(sample_index, sample_tree):
    return Chunker(sample_index, sample_tree)


def all_chunks(chunker, tree):
    """One chunk per taxonomy node, built the way the summarizer builds them."""
    chunks = []
    for node in tree.bottom_up():
        child_summaries = [(c.name, f"summary of {c.name}") for c in node.children]
        chunks.append(chunker.chunk_for(node, child_summaries=child_summaries))
    return chunks


class TestAstBoundaries:
    """No chunk may straddle a syntactic boundary."""

    def test_code_tier_chunks_map_to_exactly_one_ast_node(self, chunker, sample_tree):
        for node in sample_tree.nodes_at(Tier.CLASS) + sample_tree.nodes_at(Tier.METHOD):
            chunk = chunker.chunk_for(node)
            assert chunk.is_ast_bounded
            assert chunk.symbol_id == node.symbol_id

    def test_line_ranges_round_trip_from_the_symbol_table(
        self, chunker, sample_tree, sample_index
    ):
        registry = sample_index.build_registry()

        for node in sample_tree.nodes_at(Tier.CLASS) + sample_tree.nodes_at(Tier.METHOD):
            chunk = chunker.chunk_for(node)
            symbol = registry[node.symbol_id]

            assert chunk.file_path == symbol.file_path
            assert chunk.start_line == symbol.range.start_line
            assert chunk.end_line == symbol.range.end_line

    def test_a_method_chunk_covers_the_whole_method(self, chunker, sample_tree, sample_index):
        """A chunk that ended mid-method would have a shorter range than the symbol."""
        registry = sample_index.build_registry()

        for node in sample_tree.nodes_at(Tier.METHOD):
            chunk = chunker.chunk_for(node)
            symbol = registry[node.symbol_id]
            assert chunk.end_line - chunk.start_line == (
                symbol.range.end_line - symbol.range.start_line
            )

    def test_no_chunk_splits_a_sibling_apart(self, chunker, sample_tree, sample_index):
        """Sibling methods must occupy disjoint ranges — no overlap, no gap-filling."""
        registry = sample_index.build_registry()

        for class_node in sample_tree.nodes_at(Tier.CLASS):
            ranges = sorted(
                (registry[m.symbol_id].range.start_line, registry[m.symbol_id].range.end_line)
                for m in class_node.children
            )
            for (_, prev_end), (next_start, _) in zip(ranges, ranges[1:]):
                assert prev_end < next_start, (
                    f"overlapping method ranges in {class_node.name}"
                )

    def test_aggregating_tiers_carry_no_symbol(self, chunker, sample_tree):
        for tier in (Tier.REPOSITORY, Tier.MODULE, Tier.CONTAINER, Tier.COMPONENT):
            for node in sample_tree.nodes_at(tier):
                chunk = chunker.chunk_for(node, child_summaries=[("x", "y")])
                assert chunk.symbol_id is None
                assert chunk.is_ast_bounded is False

    def test_every_node_produces_exactly_one_chunk(self, chunker, sample_tree):
        chunks = all_chunks(chunker, sample_tree)
        node_ids = [n.node_id for n in sample_tree.bottom_up()]

        assert len(chunks) == len(node_ids)
        assert [c.node_id for c in chunks] == node_ids


class TestAggregateChunks:
    """Tiers 1-4 consume summaries, never code."""

    def test_aggregate_text_is_the_child_summary_digest(self, chunker, sample_tree):
        component = sample_tree.nodes_at(Tier.COMPONENT)[0]
        chunk = chunker.chunk_for(
            component, child_summaries=[("Alpha", "Does alpha things.")]
        )

        assert "- Alpha: Does alpha things." in chunk.text

    def test_aggregate_falls_back_to_naming_children(self, chunker, sample_tree):
        """An empty digest must still leave the prompt something structural."""
        module = sample_tree.nodes_at(Tier.MODULE)[0]
        chunk = chunker.chunk_for(module, child_summaries=[])

        assert chunk.text
        for child in module.children:
            assert child.name in chunk.text

    def test_repository_chunk_contains_no_source(self, chunker, sample_tree):
        root = sample_tree.root
        chunk = chunker.chunk_for(
            root, child_summaries=[(c.name, "A module summary.") for c in root.children]
        )

        assert "Class:" not in chunk.text
        assert "public" not in chunk.text


class TestLazySourceLoading:
    """``read_source_range`` is the only place Epic 3 touches source."""

    def test_returns_exactly_the_requested_lines(self, chunker, sample_repo_dir):
        path = "billing/payment-service/src/main/java/com/acme/billing/payment/PaymentProcessor.java"
        lines = (sample_repo_dir / path).read_text(encoding="utf-8").splitlines()

        assert chunker.read_source_range(path, 10, 13) == "\n".join(lines[9:13])

    def test_range_is_inclusive_and_one_based(self, chunker):
        path = "billing/payment-service/src/main/java/com/acme/billing/payment/PaymentProcessor.java"
        first = chunker.read_source_range(path, 1, 1)

        assert first == "package com.acme.billing.payment;"

    def test_symbol_source_matches_its_recorded_range(self, chunker, sample_index):
        symbol = sample_index.build_registry()[
            "com.acme.billing.payment.PaymentProcessor.charge"
        ]
        source = chunker.read_symbol_source(symbol.symbol_id)

        assert "charge" in source
        # This is the one place a body legitimately appears.
        assert "compareTo" in source

    def test_invalid_ranges_are_rejected(self, chunker):
        path = "billing/payment-service/src/main/java/com/acme/billing/payment/PaymentProcessor.java"

        with pytest.raises(ValueError):
            chunker.read_source_range(path, 0, 5)
        with pytest.raises(ValueError):
            chunker.read_source_range(path, 10, 3)

    def test_unknown_symbol_raises(self, chunker):
        with pytest.raises(KeyError):
            chunker.read_symbol_source("com.acme.NoSuchType")

    def test_missing_file_degrades_to_empty(self, chunker):
        assert chunker.read_source_range("does/not/exist.java", 1, 5) == ""

    def test_oversized_excerpts_are_capped(self, chunker):
        path = "billing/payment-service/src/main/java/com/acme/billing/payment/PaymentProcessor.java"
        capped = chunker.read_source_range(path, 1, 60, max_tokens=10)

        assert "more lines omitted" in capped


class TestGrounding:
    """Referenced symbols must resolve against the registry."""

    def test_references_resolve_to_real_symbols(self, chunker, sample_tree, sample_index):
        registry = sample_index.build_registry()

        for node in sample_tree.nodes_at(Tier.CLASS):
            chunk = chunker.chunk_for(node)
            for reference in chunk.referenced_symbols:
                assert reference in registry

    def test_class_chunk_picks_up_interface_references(self, chunker, sample_tree):
        processor = next(
            n for n in sample_tree.nodes_at(Tier.CLASS) if n.name == "PaymentProcessor"
        )
        chunk = chunker.chunk_for(processor)

        assert "com.acme.billing.payment.PaymentGateway" in chunk.referenced_symbols


class TestChunkModel:

    def test_is_ast_bounded_tracks_the_symbol(self):
        assert Chunk("a", Tier.CLASS, "A", "text", symbol_id="A").is_ast_bounded
        assert not Chunk("a", Tier.MODULE, "A", "text").is_ast_bounded
