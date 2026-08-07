"""Shared test fixtures for the backend test suite.

Covers both the Core Indexing Engine (Epic 1) and the AI Analysis Engine
(Epic 3).  The Epic 3 fixtures deserialise ``sample_repository_index.json`` —
a real ``core_indexing`` run over ``fixtures/sample_repo`` — and repoint its
``repository_path`` at wherever the checkout happens to live, so the lazy
source-loading path reads genuine files on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
JAVA_FIXTURES_DIR = FIXTURES_DIR / "java"
CSHARP_FIXTURES_DIR = FIXTURES_DIR / "csharp"

SAMPLE_REPO_DIR = FIXTURES_DIR / "sample_repo"
SAMPLE_INDEX_FILE = FIXTURES_DIR / "sample_repository_index.json"
SAMPLE_OVERVIEW_FILE = FIXTURES_DIR / "sample_structure_overview.json"
SAMPLE_OVERVIEW_REAL_FILE = FIXTURES_DIR / "sample_structure_overview_real.json"

#: Placeholder written into the committed fixture in place of an absolute path.
REPO_PATH_PLACEHOLDER = "<SAMPLE_REPO>"


@pytest.fixture
def java_fixtures_dir() -> Path:
    return JAVA_FIXTURES_DIR


@pytest.fixture
def csharp_fixtures_dir() -> Path:
    return CSHARP_FIXTURES_DIR


def read_fixture(path: Path) -> str:
    """Read a fixture file and return its content."""
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Epic 3 — AI Analysis Engine
# ---------------------------------------------------------------------------

def _load_sample_index_dict() -> dict:
    data = json.loads(SAMPLE_INDEX_FILE.read_text(encoding="utf-8"))
    data["repository_path"] = str(SAMPLE_REPO_DIR)
    return data


@pytest.fixture
def sample_repo_dir() -> Path:
    """The on-disk multi-module Java + C# repository behind the IR fixture."""
    return SAMPLE_REPO_DIR


@pytest.fixture
def sample_index():
    """The fixture ``RepositoryIndex``, pointed at the real sample repo."""
    from ai_analysis.ir_models import RepositoryIndex

    return RepositoryIndex.model_validate(_load_sample_index_dict())


@pytest.fixture
def stub_overview():
    """Epic 1's actual output — a single module holding ``MainContainer``."""
    from ai_analysis.ir_models import StructureOverview

    return StructureOverview.model_validate(
        json.loads(SAMPLE_OVERVIEW_FILE.read_text(encoding="utf-8"))
    )


@pytest.fixture
def real_overview():
    """An overview carrying genuine Module/Container tiers.

    Shaped per ``docs/designs/taxonomy-input-contract.md`` — what Epic 1 is
    expected to emit once it detects build files.
    """
    from ai_analysis.ir_models import StructureOverview

    return StructureOverview.model_validate(
        json.loads(SAMPLE_OVERVIEW_REAL_FILE.read_text(encoding="utf-8"))
    )


@pytest.fixture
def sample_tree(sample_index):
    """The 6-tier taxonomy built by the heuristic provider."""
    from ai_analysis.taxonomy.heuristic import HeuristicTaxonomyProvider

    return HeuristicTaxonomyProvider().build(sample_index)


@pytest.fixture
def sample_index_dir(tmp_path) -> Path:
    """A throwaway ``indexes/`` directory holding both fixture JSON files.

    Gives the CLI and the loader a directory to consume without depending on a
    prior ``core_indexing`` run.
    """
    index_dir = tmp_path / "indexes"
    index_dir.mkdir()

    (index_dir / "repository_index.json").write_text(
        json.dumps(_load_sample_index_dict()), encoding="utf-8"
    )
    (index_dir / "structure_overview.json").write_text(
        SAMPLE_OVERVIEW_FILE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return index_dir
