"""Unit tests for the RepositoryScanner (US-1.1, US-1.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core_indexing.models import DirectoryNode, Language
from core_indexing.scanner import RepositoryScanner
from tests.conftest import FIXTURES_DIR


@pytest.fixture
def scanner_output_dir(tmp_path: Path) -> Path:
    return tmp_path / "indexes"


class TestRepositoryScanner:
    def test_invalid_local_path(self, scanner_output_dir: Path):
        scanner = RepositoryScanner(
            target="non_existent_directory_12345",
            output_dir=str(scanner_output_dir),
        )
        with pytest.raises(ValueError, match="Invalid local repository path"):
            scanner.prepare_repository()

    def test_git_url_detection(self):
        assert RepositoryScanner._is_git_url("https://github.com/example/repo.git")
        assert RepositoryScanner._is_git_url("git@github.com:example/repo.git")
        assert RepositoryScanner._is_git_url("https://github.com/example/repo")
        assert not RepositoryScanner._is_git_url("./local/path")
        assert not RepositoryScanner._is_git_url("C:\\path\\to\\repo")

    def test_scan_local_fixtures_directory(self, scanner_output_dir: Path):
        scanner = RepositoryScanner(
            target=str(FIXTURES_DIR),
            output_dir=str(scanner_output_dir),
        )
        tree, file_indexes = scanner.scan_and_parse()

        # Check directory tree
        assert isinstance(tree, DirectoryNode)
        assert len(tree.children) >= 2  # java and csharp subdirs

        # Check saved structure file (US-1.2)
        structure_file = scanner_output_dir / "structure.json"
        assert structure_file.exists()
        saved_data = json.loads(structure_file.read_text(encoding="utf-8"))
        assert "name" in saved_data
        assert "children" in saved_data

        # Check parsed files
        assert len(file_indexes) >= 4  # Java & C# fixtures
        languages = {f.language for f in file_indexes}
        assert Language.JAVA in languages
        assert Language.CSHARP in languages
