"""Taxonomy provider tests (FR-13, US-3.3, US-3.4).

Covers both halves of the swappable-provider design in
``ai_analysis/taxonomy/provider.py``: that ``resolve_provider`` correctly tells
Epic 1's ``MainContainer`` stub apart from real tier data, and that the
heuristic fallback recovers Modules and Containers from build files when it has
to.
"""

from __future__ import annotations

import pytest

from ai_analysis.models import Tier
from ai_analysis.taxonomy.from_index import IndexTaxonomyProvider
from ai_analysis.taxonomy.heuristic import (
    HeuristicTaxonomyProvider,
    find_containers,
    module_name_for,
)
from ai_analysis.taxonomy.provider import has_real_tiers, resolve_provider


class TestProviderSelection:
    """``resolve_provider`` must not be fooled by the stub."""

    def test_stub_overview_falls_back_to_heuristic(self, stub_overview):
        assert has_real_tiers(stub_overview) is False
        assert isinstance(resolve_provider(stub_overview), HeuristicTaxonomyProvider)

    def test_real_overview_selects_index_provider(self, real_overview):
        assert has_real_tiers(real_overview) is True
        assert isinstance(resolve_provider(real_overview), IndexTaxonomyProvider)

    def test_missing_overview_falls_back_to_heuristic(self):
        assert has_real_tiers(None) is False
        assert isinstance(resolve_provider(None), HeuristicTaxonomyProvider)

    def test_containers_without_a_path_are_not_real_tiers(self, real_overview):
        """A named container with no path corresponds to nothing on disk."""
        for module in real_overview.modules:
            for container in module["containers"]:
                container.pop("path")

        assert has_real_tiers(real_overview) is False

    def test_force_overrides_detection(self, real_overview):
        assert isinstance(
            resolve_provider(real_overview, force="heuristic"), HeuristicTaxonomyProvider
        )
        assert isinstance(
            resolve_provider(None, force="index"), IndexTaxonomyProvider
        )

    def test_unknown_force_value_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown taxonomy provider"):
            resolve_provider(None, force="magic")


class TestContainerDetection:
    """Build files are what mark a deployable unit."""

    def test_finds_maven_and_dotnet_containers(self, sample_repo_dir):
        found = dict(find_containers(sample_repo_dir))

        assert found["billing/payment-service"] == "billing/payment-service/pom.xml"
        assert found["billing/invoice-service"] == "billing/invoice-service/pom.xml"
        assert found["identity/IdentityApi"] == "identity/IdentityApi/IdentityApi.csproj"

    def test_detection_is_deterministic(self, sample_repo_dir):
        assert find_containers(sample_repo_dir) == find_containers(sample_repo_dir)

    def test_directories_without_build_files_are_not_containers(self, sample_repo_dir):
        found = dict(find_containers(sample_repo_dir))
        assert "billing" not in found
        assert "identity" not in found

    @pytest.mark.parametrize(
        "container_dir,expected",
        [
            ("billing/payment-service", ("billing", "billing")),
            ("payment-service", ("acme", ".")),
            (".", ("acme", ".")),
        ],
    )
    def test_module_derived_from_parent_directory(self, container_dir, expected):
        assert module_name_for(container_dir, "acme") == expected


class TestHeuristicTree:
    """The six tiers assembled from build files plus the AST."""

    def test_modules_and_containers_are_recovered(self, sample_tree):
        modules = {m.name for m in sample_tree.nodes_at(Tier.MODULE)}
        containers = {c.name for c in sample_tree.nodes_at(Tier.CONTAINER)}

        assert modules == {"billing", "identity"}
        assert containers == {"payment-service", "invoice-service", "IdentityApi"}

    def test_every_tier_is_populated(self, sample_tree):
        for tier in Tier:
            assert sample_tree.nodes_at(tier), f"tier {tier.name} is empty"

    def test_containers_record_their_marker_file(self, sample_tree):
        payment = next(
            c for c in sample_tree.nodes_at(Tier.CONTAINER) if c.name == "payment-service"
        )
        assert payment.marker_file == "billing/payment-service/pom.xml"

    def test_provenance_is_recorded_as_heuristic(self, sample_tree):
        assert sample_tree.provider == "heuristic"
        assert all(n.derived_by == "heuristic" for n in sample_tree.root.walk())

    def test_symbols_land_in_the_container_owning_their_file(self, sample_tree):
        payment = next(
            c for c in sample_tree.nodes_at(Tier.CONTAINER) if c.name == "payment-service"
        )
        classes = {c.name for c in payment.nodes_at(Tier.CLASS)}

        assert "PaymentProcessor" in classes
        assert "InvoiceRenderer" not in classes

    def test_components_are_packages_and_namespaces(self, sample_tree):
        components = {c.name for c in sample_tree.nodes_at(Tier.COMPONENT)}
        assert "com.acme.billing.payment" in components
        assert "Acme.Identity.Controllers" in components

    def test_only_callables_become_method_tier_nodes(self, sample_tree, sample_index):
        registry = sample_index.build_registry()
        for node in sample_tree.nodes_at(Tier.METHOD):
            assert registry[node.symbol_id].is_callable

    def test_bottom_up_yields_children_before_parents(self, sample_tree):
        order = [n.node_id for n in sample_tree.bottom_up()]
        position = {node_id: i for i, node_id in enumerate(order)}

        for node in sample_tree.root.walk():
            for child in node.children:
                assert position[child.node_id] < position[node.node_id]


class TestIndexTree:
    """The preferred path, once Epic 1 supplies real tiers."""

    def test_tiers_are_read_from_the_overview(self, sample_index, real_overview):
        tree = IndexTaxonomyProvider().build(sample_index, real_overview)

        assert tree.provider == "index"
        assert {m.name for m in tree.nodes_at(Tier.MODULE)} == {"billing", "identity"}
        assert {c.name for c in tree.nodes_at(Tier.CONTAINER)} == {
            "payment-service", "invoice-service", "IdentityApi"
        }

    def test_matches_what_the_heuristic_infers(self, sample_index, real_overview, sample_tree):
        """The fallback is only useful if it reproduces the real answer."""
        from_index = IndexTaxonomyProvider().build(sample_index, real_overview)

        assert {c.name for c in from_index.nodes_at(Tier.CONTAINER)} == {
            c.name for c in sample_tree.nodes_at(Tier.CONTAINER)
        }
        assert {c.name for c in from_index.nodes_at(Tier.CLASS)} == {
            c.name for c in sample_tree.nodes_at(Tier.CLASS)
        }

    def test_requires_an_overview(self, sample_index):
        with pytest.raises(ValueError, match="requires a structure_overview"):
            IndexTaxonomyProvider().build(sample_index, None)
