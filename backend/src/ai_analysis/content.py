"""The four wiki content areas (``docs/epics.md`` Epic 3 scope).

Epic 3 does not only build the taxonomy — it also produces the prose for the four
views the wiki renders:

===============  ===========================  ===============================
Content area     Requirement                  Rendered by Epic 4 into
===============  ===========================  ===============================
``tech``         US-4.1, FR-4                 ``wiki/tech.html``
``tests``        US-4.2, FR-5                 ``wiki/tests.html``
``architecture`` US-3.3, US-4.3, FR-6         ``wiki/architecture.html``
``modules``      US-3.4, US-4.4, FR-7         ``wiki/modules/*.html``
===============  ===========================  ===============================

Every section carries a ``facts`` mapping alongside its prose.  The facts are
derived deterministically from the symbol table and build files, so they hold
even with no LLM (US-3.2) and give Epic 4 structured data to render as tables
rather than re-parsing prose.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from ai_analysis.ir_models import ASTSymbolNode, Language, RepositoryIndex
from ai_analysis.llm.base import LLMClient
from ai_analysis.models import ContentSection, SummaryNode, TaxonomyTree, Tier
from ai_analysis.prompts import SYSTEM_PROMPT
from ai_analysis.tokens import DEFAULT_BUDGET, count_tokens

logger = logging.getLogger(__name__)

#: Annotations that identify a symbol as test infrastructure.
TEST_ANNOTATIONS = frozenset({
    "Test", "ParameterizedTest", "RepeatedTest", "BeforeEach", "AfterEach",  # JUnit 5
    "BeforeAll", "AfterAll", "Disabled",
    "Fact", "Theory",                                                        # xUnit
    "TestMethod", "TestClass", "TestInitialize",                             # MSTest
    "SetUp", "TearDown", "TestFixture",                                      # NUnit
})

#: Import prefix → framework name.  Ordered longest-first at match time so that
#: a more specific prefix wins over a more general one.
FRAMEWORK_BY_IMPORT: Dict[str, str] = {
    "org.springframework.boot": "Spring Boot",
    "org.springframework": "Spring Framework",
    "jakarta.persistence": "Jakarta Persistence (JPA)",
    "javax.persistence": "Java Persistence (JPA)",
    "org.junit.jupiter": "JUnit 5",
    "org.junit": "JUnit 4",
    "org.mockito": "Mockito",
    "org.hibernate": "Hibernate",
    "com.fasterxml.jackson": "Jackson",
    "lombok": "Lombok",
    "Microsoft.AspNetCore": "ASP.NET Core",
    "Microsoft.EntityFrameworkCore": "Entity Framework Core",
    "Microsoft.Extensions": "Microsoft.Extensions",
    "Xunit": "xUnit",
    "NUnit": "NUnit",
    "Moq": "Moq",
    "Newtonsoft.Json": "Json.NET",
    "AutoMapper": "AutoMapper",
    "Serilog": "Serilog",
}

#: Build files → the toolchain they imply.
BUILD_TOOLS: Dict[str, str] = {
    "pom.xml": "Maven",
    "build.gradle": "Gradle",
    "build.gradle.kts": "Gradle (Kotlin DSL)",
    "settings.gradle": "Gradle",
    "package.json": "npm",
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
}

#: Architectural layer → the annotations and name suffixes that signal it.
LAYER_SIGNALS: Dict[str, tuple] = {
    "Presentation / API": (
        {"RestController", "Controller", "ApiController", "RequestMapping", "Route"},
        ("Controller", "Resource", "Endpoint", "Api"),
    ),
    "Application / Service": (
        {"Service", "Component", "Transactional"},
        ("Service", "Manager", "Handler", "UseCase", "Processor"),
    ),
    "Persistence": (
        {"Repository", "Entity", "Table"},
        ("Repository", "Dao", "Entity", "Store"),
    ),
    "Configuration": (
        {"Configuration", "ConfigurationProperties", "Bean"},
        ("Config", "Configuration", "Settings", "Options"),
    ),
    "Testing": (TEST_ANNOTATIONS, ("Test", "Tests", "Spec", "IT")),
}


class ContentGenerator:
    """Produces the four wiki content sections."""

    def __init__(
        self,
        index: RepositoryIndex,
        tree: TaxonomyTree,
        summaries: Sequence[SummaryNode],
        llm: Optional[LLMClient] = None,
    ):
        self.index = index
        self.tree = tree
        self.summaries = {s.node_id: s for s in summaries}
        self.llm = llm

    def generate_all(self) -> List[ContentSection]:
        return [
            self.generate_tech(),
            self.generate_tests(),
            self.generate_architecture(),
            self.generate_modules(),
        ]

    # ------------------------------------------------------------------
    # Tech (US-4.1, FR-4)
    # ------------------------------------------------------------------

    def generate_tech(self) -> ContentSection:
        facts = {
            "languages": [l.value for l in self.index.languages],
            "frameworks": self.detect_frameworks(),
            "build_tools": self.detect_build_tools(),
            "containers": [c.name for c in self.tree.nodes_at(Tier.CONTAINER)],
        }

        structural = self._describe_tech(facts)
        body = self._maybe_elaborate(
            structural,
            task=(
                "Describe the technology stack of this repository: languages, "
                "frameworks, and how it is built."
            ),
            facts=facts,
        )
        return ContentSection(
            key="tech",
            title="Technology Stack",
            body=body,
            facts=facts,
            generated_by="llm" if self._llm_active else "structural",
        )

    def detect_frameworks(self) -> List[str]:
        """Frameworks inferred from import and using directives."""
        found: set[str] = set()
        prefixes = sorted(FRAMEWORK_BY_IMPORT, key=len, reverse=True)

        for file_index in self.index.files:
            for import_info in file_index.imports:
                for prefix in prefixes:
                    if import_info.name.startswith(prefix):
                        found.add(FRAMEWORK_BY_IMPORT[prefix])
                        break

        return sorted(found)

    def detect_build_tools(self) -> List[str]:
        """Toolchains inferred from build files present in the repository."""
        found: set[str] = set()
        repo_path = Path(self.index.repository_path)

        for container in self.tree.nodes_at(Tier.CONTAINER):
            if not container.marker_file:
                continue
            name = Path(container.marker_file).name
            if name in BUILD_TOOLS:
                found.add(BUILD_TOOLS[name])
            elif name.endswith((".csproj", ".fsproj", ".vbproj")):
                found.add(".NET SDK")

        if repo_path.is_dir():
            for filename, tool in BUILD_TOOLS.items():
                if (repo_path / filename).exists():
                    found.add(tool)
            if any(repo_path.glob("*.sln")):
                found.add(".NET SDK")

        return sorted(found)

    def _describe_tech(self, facts: Dict[str, List[str]]) -> str:
        parts = []
        if facts["languages"]:
            parts.append(f"Written in {self._join(facts['languages'])}.")
        if facts["frameworks"]:
            parts.append(f"Uses {self._join(facts['frameworks'])}.")
        if facts["build_tools"]:
            parts.append(f"Built with {self._join(facts['build_tools'])}.")
        if facts["containers"]:
            parts.append(
                f"Comprises {len(facts['containers'])} deployable unit(s): "
                f"{self._join(facts['containers'])}."
            )
        return " ".join(parts) or "No technology information could be determined."

    # ------------------------------------------------------------------
    # Tests (US-4.2, FR-5)
    # ------------------------------------------------------------------

    def generate_tests(self) -> ContentSection:
        test_symbols = self.find_test_symbols()
        test_types = sorted({
            s.parent_symbol_id or s.symbol_id
            for s in test_symbols
        })
        frameworks = self.detect_test_frameworks()

        facts = {
            "test_frameworks": frameworks,
            "test_types": test_types,
            "test_methods": sorted(s.fully_qualified_name for s in test_symbols if s.is_callable),
            "run_commands": self.suggest_test_commands(),
        }

        structural = self._describe_tests(facts)
        body = self._maybe_elaborate(
            structural,
            task="Describe how this repository is tested and how to run its test suite.",
            facts=facts,
        )
        return ContentSection(
            key="tests",
            title="Tests",
            body=body,
            facts=facts,
            generated_by="llm" if self._llm_active else "structural",
        )

    def find_test_symbols(self) -> List[ASTSymbolNode]:
        """Symbols carrying a test annotation, or declared by a type that does."""
        direct = [
            s for s in self.index.symbols
            if TEST_ANNOTATIONS & set(s.annotation_names)
        ]
        owners = {s.parent_symbol_id for s in direct if s.parent_symbol_id}

        return sorted(
            {s.symbol_id: s for s in direct + [
                s for s in self.index.symbols if s.symbol_id in owners
            ]}.values(),
            key=lambda s: s.symbol_id,
        )

    def detect_test_frameworks(self) -> List[str]:
        frameworks = {
            name for name in self.detect_frameworks()
            if name in {"JUnit 5", "JUnit 4", "xUnit", "NUnit", "Mockito", "Moq"}
        }
        return sorted(frameworks)

    def suggest_test_commands(self) -> List[str]:
        """Commands implied by the detected build tooling."""
        tools = set(self.detect_build_tools())
        commands = []
        if "Maven" in tools:
            commands.append("mvn test")
        if any(t.startswith("Gradle") for t in tools):
            commands.append("./gradlew test")
        if ".NET SDK" in tools:
            commands.append("dotnet test")
        return commands

    def _describe_tests(self, facts: Dict[str, List[str]]) -> str:
        if not facts["test_types"]:
            return "No test classes were detected in this repository."

        parts = [f"Contains {len(facts['test_types'])} test class(es)"]
        if facts["test_methods"]:
            parts[0] += f" declaring {len(facts['test_methods'])} test method(s)"
        parts[0] += "."

        if facts["test_frameworks"]:
            parts.append(f"Tests use {self._join(facts['test_frameworks'])}.")
        if facts["run_commands"]:
            parts.append(f"Run them with: {', '.join(facts['run_commands'])}.")

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Architecture (US-3.3, US-4.3, FR-6)
    # ------------------------------------------------------------------

    def generate_architecture(self) -> ContentSection:
        layers = self.identify_layers()
        facts = {
            "layers": sorted(layers),
            "modules": [m.name for m in self.tree.nodes_at(Tier.MODULE)],
            "containers": [c.name for c in self.tree.nodes_at(Tier.CONTAINER)],
            "components": [c.name for c in self.tree.nodes_at(Tier.COMPONENT)],
            **{f"layer:{name}": sorted(members) for name, members in layers.items()},
        }

        root_summary = self.summaries.get(self.tree.root.node_id)
        structural = self._describe_architecture(facts)
        body = root_summary.summary if root_summary and self._llm_active else structural

        return ContentSection(
            key="architecture",
            title="Architecture",
            body=body,
            facts=facts,
            generated_by="llm" if (root_summary and self._llm_active) else "structural",
        )

    def identify_layers(self) -> Dict[str, List[str]]:
        """Group types into architectural layers (US-3.3).

        Classification uses annotations first — they are declarative and
        unambiguous — then falls back to naming convention.
        """
        layers: Dict[str, List[str]] = {}

        for symbol in self.index.symbols:
            if not symbol.is_type:
                continue

            layer = self._classify(symbol)
            if layer:
                layers.setdefault(layer, []).append(symbol.fully_qualified_name)

        return layers

    @staticmethod
    def _classify(symbol: ASTSymbolNode) -> Optional[str]:
        annotations = set(symbol.annotation_names)

        for layer, (signals, _suffixes) in LAYER_SIGNALS.items():
            if annotations & signals:
                return layer

        for layer, (_signals, suffixes) in LAYER_SIGNALS.items():
            if symbol.name.endswith(suffixes):
                return layer

        return None

    def _describe_architecture(self, facts: Dict[str, List[str]]) -> str:
        parts = []
        if facts["modules"]:
            parts.append(
                f"Organised into {len(facts['modules'])} module(s): "
                f"{self._join(facts['modules'])}."
            )
        if facts["containers"]:
            parts.append(f"Deploys as {len(facts['containers'])} unit(s).")
        if facts["layers"]:
            parts.append(f"Layers identified: {self._join(facts['layers'])}.")
        return " ".join(parts) or "No architectural structure could be determined."

    # ------------------------------------------------------------------
    # Modules (US-3.4, US-4.4, FR-7)
    # ------------------------------------------------------------------

    def generate_modules(self) -> ContentSection:
        module_nodes = self.tree.nodes_at(Tier.MODULE)

        facts: Dict[str, List[str]] = {"modules": [m.name for m in module_nodes]}
        lines: List[str] = []

        for module in module_nodes:
            summary = self.summaries.get(module.node_id)
            text = summary.summary if summary else "No summary available."
            lines.append(f"{module.name}: {text}")

            facts[f"module:{module.name}"] = [
                c.name for c in module.nodes_at(Tier.CONTAINER)
            ]

        return ContentSection(
            key="modules",
            title="Modules",
            body="\n\n".join(lines) or "No modules were identified.",
            facts=facts,
            generated_by="llm" if self._llm_active else "structural",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def _llm_active(self) -> bool:
        return self.llm is not None and self.llm.enabled

    def _maybe_elaborate(
        self,
        structural: str,
        *,
        task: str,
        facts: Dict[str, List[str]],
    ) -> str:
        """Ask the model to write prose over the structural facts, if enabled.

        The facts are always supplied verbatim, so the model rephrases evidence
        rather than inventing it.  Any failure returns the structural text — a
        missing LLM must never interrupt execution (US-3.2).
        """
        if not self._llm_active:
            return structural

        evidence = "\n".join(
            f"{key}: {', '.join(values)}" for key, values in facts.items() if values
        )
        prompt = (
            "STRUCTURAL FACTS\n"
            f"{evidence}\n\n"
            "TASK INSTRUCTION\n"
            f"{task}\n"
            "Use only the facts above. Answer in under 120 words, plain prose."
        )

        if count_tokens(prompt) > DEFAULT_BUDGET:
            return structural

        try:
            response = self.llm.generate(prompt, system=SYSTEM_PROMPT)
        except Exception as exc:  # noqa: BLE001 - never abort content generation
            logger.warning("Content elaboration failed, using structural text: %s", exc)
            return structural

        return response.text.strip() or structural

    @staticmethod
    def _join(items: Sequence[str]) -> str:
        items = list(items)
        if len(items) <= 1:
            return "".join(items)
        return ", ".join(items[:-1]) + f" and {items[-1]}"
