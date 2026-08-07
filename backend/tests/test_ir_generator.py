"""End-to-end unit tests for RepositoryIndexer and IRGenerator (US-1.1 - US-1.4)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core_indexing.indexer import RepositoryIndexer
from core_indexing.ir_generator import IRGenerator
from core_indexing.models import Language, RepositoryIndex, SymbolKind
from core_indexing.scanner import RepositoryScanner
from tests.conftest import FIXTURES_DIR


@pytest.fixture
def scanned_repo(tmp_path: Path):
    output_dir = tmp_path / "indexes"
    scanner = RepositoryScanner(
        target=str(FIXTURES_DIR),
        output_dir=str(output_dir),
    )
    tree, file_indexes = scanner.scan_and_parse()
    return tree, file_indexes, output_dir


class TestIndexerAndIRGenerator:
    def test_repository_indexer(self, scanned_repo):
        tree, file_indexes, output_dir = scanned_repo

        indexer = RepositoryIndexer(
            repository_name="TestFixturesRepo",
            repository_path=str(FIXTURES_DIR),
            directory_tree=tree,
            file_indexes=file_indexes,
        )
        repo_index = indexer.build_index()

        assert isinstance(repo_index, RepositoryIndex)
        assert repo_index.repository_name == "TestFixturesRepo"
        assert len(repo_index.symbols) > 0
        assert len(repo_index.relationships) > 0

        # Verify Java and C# symbols are present
        symbol_kinds = {s.kind for s in repo_index.symbols}
        assert SymbolKind.CLASS in symbol_kinds
        assert SymbolKind.INTERFACE in symbol_kinds
        assert SymbolKind.METHOD in symbol_kinds

    def test_ir_generator(self, scanned_repo):
        tree, file_indexes, output_dir = scanned_repo

        indexer = RepositoryIndexer(
            repository_name="TestFixturesRepo",
            repository_path=str(FIXTURES_DIR),
            directory_tree=tree,
            file_indexes=file_indexes,
        )
        repo_index = indexer.build_index()

        ir_gen = IRGenerator(index=repo_index, output_dir=str(output_dir))
        repo_index_path, overview_path = ir_gen.generate_all()

        # Check repository_index.json
        assert repo_index_path.exists()
        repo_data = json.loads(repo_index_path.read_text(encoding="utf-8"))
        assert repo_data["repository_name"] == "TestFixturesRepo"
        assert len(repo_data["symbols"]) == len(repo_index.symbols)

        # Check structure_overview.json
        assert overview_path.exists()
        overview_data = json.loads(overview_path.read_text(encoding="utf-8"))
        assert overview_data["repository"] == "TestFixturesRepo"
        assert "modules" in overview_data
        assert overview_data["total_symbols"] == len(repo_index.symbols)
