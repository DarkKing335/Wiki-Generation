"""Content generation tests — the four wiki areas (``docs/epics.md`` Epic 3).

===============  ===========================
Content area     Requirement
===============  ===========================
``tech``         US-4.1, FR-4
``tests``        US-4.2, FR-5
``architecture`` US-3.3, US-4.3, FR-6
``modules``      US-3.4, US-4.4, FR-7
===============  ===========================

Each section carries a ``facts`` mapping derived deterministically from the
symbol table and build files.  The facts are what Epic 4 renders as tables, and
what keeps the prose honest — so they are asserted directly rather than through
the generated text.
"""

from __future__ import annotations

import pytest

from ai_analysis.content import ContentGenerator
from ai_analysis.llm.null import NullLLMClient
from ai_analysis.models import Tier
from ai_analysis.summarizer import Summarizer


@pytest.fixture
def generator(sample_index, sample_tree):
    summaries = Summarizer(sample_index, sample_tree, NullLLMClient()).run()
    return ContentGenerator(sample_index, sample_tree, summaries, llm=NullLLMClient())


class TestSectionSet:

    def test_all_four_areas_are_produced_in_order(self, generator):
        assert [s.key for s in generator.generate_all()] == [
            "tech", "tests", "architecture", "modules"
        ]

    def test_every_section_has_a_title_and_body(self, generator):
        for section in generator.generate_all():
            assert section.title
            assert section.body.strip()

    def test_sections_are_marked_structural_without_a_model(self, generator):
        for section in generator.generate_all():
            assert section.generated_by == "structural"


class TestTechStack:
    """US-4.1 / FR-4 — languages, frameworks and toolchain."""

    def test_both_languages_are_reported(self, generator):
        facts = generator.generate_tech().facts
        assert set(facts["languages"]) == {"java", "csharp"}

    def test_frameworks_are_inferred_from_imports(self, generator):
        frameworks = generator.detect_frameworks()

        assert "Spring Framework" in frameworks
        assert "ASP.NET Core" in frameworks

    def test_build_tools_are_inferred_from_marker_files(self, generator):
        tools = generator.detect_build_tools()

        assert "Maven" in tools
        assert ".NET SDK" in tools

    def test_containers_are_listed(self, generator):
        containers = generator.generate_tech().facts["containers"]

        assert set(containers) == {"payment-service", "invoice-service", "IdentityApi"}

    def test_the_prose_reflects_the_facts(self, generator):
        body = generator.generate_tech().body

        assert "Maven" in body
        assert "deployable unit" in body


class TestTestInfrastructure:
    """US-4.2 / FR-5 — detection via ``@Test`` and ``[Fact]``."""

    def test_junit_annotated_methods_are_found(self, generator):
        methods = generator.generate_tests().facts["test_methods"]

        assert any("chargeRejectsAmountsBelowMinimum" in m for m in methods)

    def test_xunit_annotated_methods_are_found(self, generator):
        methods = generator.generate_tests().facts["test_methods"]

        assert any("FindAsyncReturnsNullForUnknownId" in m for m in methods)

    def test_the_declaring_test_classes_are_recorded(self, generator):
        types = generator.generate_tests().facts["test_types"]

        assert "com.acme.billing.payment.PaymentProcessorTest" in types
        assert "Acme.Identity.Services.UserServiceTests" in types

    def test_both_test_frameworks_are_identified(self, generator):
        frameworks = generator.detect_test_frameworks()

        assert "JUnit 5" in frameworks
        assert "xUnit" in frameworks

    def test_run_commands_follow_the_build_tooling(self, generator):
        commands = generator.suggest_test_commands()

        assert "mvn test" in commands
        assert "dotnet test" in commands

    def test_production_classes_are_not_reported_as_tests(self, generator):
        types = generator.generate_tests().facts["test_types"]

        assert "com.acme.billing.payment.PaymentProcessor" not in types

    def test_lifecycle_annotations_count_as_test_infrastructure(self, generator):
        """``@BeforeEach`` marks a class as test infrastructure too."""
        found = {s.fully_qualified_name for s in generator.find_test_symbols()}

        assert "com.acme.billing.payment.PaymentProcessorTest.setUp" in found


class TestArchitectureLayers:
    """US-3.3 / US-4.3 / FR-6 — layer identification."""

    def test_service_annotated_types_land_in_the_service_layer(self, generator):
        layers = generator.identify_layers()

        assert "com.acme.billing.payment.PaymentProcessor" in layers["Application / Service"]

    def test_api_controllers_land_in_the_presentation_layer(self, generator):
        layers = generator.identify_layers()

        assert "Acme.Identity.Controllers.UserController" in layers["Presentation / API"]

    def test_test_classes_land_in_the_testing_layer(self, generator):
        layers = generator.identify_layers()

        assert "com.acme.billing.payment.PaymentProcessorTest" in layers["Testing"]

    def test_naming_convention_classifies_when_annotations_are_absent(self, generator):
        """``UserService`` carries no attribute but its suffix is unambiguous."""
        layers = generator.identify_layers()

        assert "Acme.Identity.Services.UserService" in layers["Application / Service"]

    def test_layers_are_exposed_as_facts_for_epic_4(self, generator):
        facts = generator.generate_architecture().facts

        assert "Presentation / API" in facts["layers"]
        assert facts["layer:Presentation / API"]

    def test_modules_and_containers_are_listed(self, generator):
        facts = generator.generate_architecture().facts

        assert set(facts["modules"]) == {"billing", "identity"}
        assert len(facts["containers"]) == 3


class TestModuleResponsibilities:
    """US-3.4 / US-4.4 / FR-7 — per-module prose."""

    def test_every_module_appears_in_the_body(self, generator, sample_tree):
        body = generator.generate_modules().body

        for module in sample_tree.nodes_at(Tier.MODULE):
            assert module.name in body

    def test_each_module_maps_to_its_containers(self, generator):
        facts = generator.generate_modules().facts

        assert set(facts["module:billing"]) == {"payment-service", "invoice-service"}
        assert facts["module:identity"] == ["IdentityApi"]

    def test_module_summaries_come_from_the_summarizer(self, generator):
        body = generator.generate_modules().body

        assert "No summary available." not in body


class TestNoModelDegradation:
    """A missing model must never interrupt content generation (US-3.2)."""

    def test_generation_works_with_no_llm_at_all(self, sample_index, sample_tree):
        summaries = Summarizer(sample_index, sample_tree, NullLLMClient()).run()
        sections = ContentGenerator(
            sample_index, sample_tree, summaries, llm=None
        ).generate_all()

        assert len(sections) == 4
        assert all(s.body.strip() for s in sections)

    def test_a_raising_model_falls_back_to_structural_text(self, sample_index, sample_tree):
        from ai_analysis.llm.base import LLMClient

        class BrokenClient(LLMClient):
            name = "broken"
            enabled = True

            def generate(self, prompt, *, system=None, tools=None, max_tokens=None):
                raise RuntimeError("model exploded")

        summaries = Summarizer(sample_index, sample_tree, NullLLMClient()).run()
        sections = ContentGenerator(
            sample_index, sample_tree, summaries, llm=BrokenClient()
        ).generate_all()

        assert len(sections) == 4
        assert all(s.body.strip() for s in sections)
