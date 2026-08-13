"""Repository Scanner — Implements US-1.1 and US-1.2.

Features:
- Accepts local paths or Git URLs (clones remote repos if needed).
- Scans repository directory structure respecting .gitignore rules.
- Identifies supported source files (.java, .cs).
- Saves repository directory structure locally (indexes/structure.json).
- Routes files to appropriate language parsers.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pathspec

from core_indexing.models import DirectoryNode, FileIndex, Language
from core_indexing.parsers.base import BaseLanguageParser
from core_indexing.parsers.csharp_parser import CSharpParser
from core_indexing.parsers.java_parser import JavaParser

logger = logging.getLogger(__name__)

# Default directory & file patterns to ignore if not in .gitignore
DEFAULT_EXCLUDES = {
    ".git", ".svn", ".hg", ".idea", ".vscode", "__pycache__",
    "node_modules", "bin", "obj", "target", "build", ".gradle",
}


class RepositoryScanner:
    """Scans local or remote repositories for Java and C# code structures."""

    def __init__(self, target: str, output_dir: Optional[str] = None):
        """
        Parameters
        ----------
        target:
            Local file path or Git repository URL.
        output_dir:
            Directory where saved structure and index files will be stored.
            Defaults to ``RepoAtlas/indexes`` or current working dir ``indexes``.
        """
        self.target = target
        self.output_dir = Path(output_dir) if output_dir else Path("indexes")
        self.is_remote = self._is_git_url(target)
        self.repo_path: Path = Path()
        self._temp_dir: Optional[str] = None

        # Registered parsers
        self.parsers: Dict[str, BaseLanguageParser] = {
            ".java": JavaParser(),
            ".cs": CSharpParser(),
        }

    @staticmethod
    def _is_git_url(target: str) -> bool:
        """Check if target string is a Git URL or remote repository shorthand."""
        target_str = target.strip()
        git_patterns = [
            r"^https?://.*\.git$",
            r"^git@.*:.*\.git$",
            r"^https?://github\.com/.*",
            r"^https?://gitlab\.com/.*",
            r"^https?://bitbucket\.org/.*",
        ]
        if any(re.match(pat, target_str) for pat in git_patterns):
            return True

        # Local filesystem paths (relative or absolute) are never remote git URLs
        if target_str.startswith((".", "/", "\\")) or Path(target_str).is_absolute():
            return False

        # Check shorthand format like owner/repo or owner/repo.git if local path does not exist
        if re.match(r"^[\w\.-]+/[\w\.-]+(?:\.git)?$", target_str):
            if not Path(target_str).exists():
                return True

        return False

    def prepare_repository(self) -> Path:
        """Prepare repository path: clone if Git URL, or validate local path."""
        if self.is_remote:
            url = self.target.strip()
            if not url.startswith(("http://", "https://", "git@")):
                url = f"https://github.com/{url}"
                if not url.endswith(".git"):
                    url += ".git"
            self.target = url
            logger.info(f"Cloning remote repository: {self.target}")
            print(f"  -> Dang clone git repository tu: {self.target}...")
            self._temp_dir = tempfile.mkdtemp(prefix="repoatlas_repo_")
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", self.target, self._temp_dir],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.repo_path = Path(self._temp_dir).resolve()
            except subprocess.CalledProcessError as e:
                self.cleanup()
                raise ValueError(f"Failed to clone repository from '{self.target}': {e.stderr}") from e
        else:
            local_path = Path(self.target).resolve()
            if not local_path.exists() or not local_path.is_dir():
                raise ValueError(f"Invalid local repository path: '{self.target}'")
            self.repo_path = local_path

        return self.repo_path

    def load_gitignore(self) -> Optional[pathspec.PathSpec]:
        """Load .gitignore rules if present in the repository root."""
        gitignore_file = self.repo_path / ".gitignore"
        if gitignore_file.exists():
            try:
                patterns = gitignore_file.read_text(encoding="utf-8").splitlines()
                return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
            except Exception as e:
                logger.warning(f"Could not parse .gitignore file: {e}")
        return None

    def scan_structure(self) -> DirectoryNode:
        """Build the directory tree node structure respecting ignore patterns."""
        spec = self.load_gitignore()

        def _build_tree(current_path: Path, rel_path: str = "") -> DirectoryNode:
            node_name = current_path.name or str(current_path)
            node = DirectoryNode(
                name=node_name,
                path=rel_path or ".",
                is_directory=current_path.is_dir(),
                children=[],
            )

            if not current_path.is_dir():
                ext = current_path.suffix.lower()
                if ext == ".java":
                    node.language = Language.JAVA
                elif ext == ".cs":
                    node.language = Language.CSHARP
                return node

            try:
                entries = sorted(list(current_path.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                return node

            for entry in entries:
                if entry.name in DEFAULT_EXCLUDES:
                    continue

                entry_rel = entry.relative_to(self.repo_path).as_posix()

                if spec and spec.match_file(entry_rel):
                    continue

                child_node = _build_tree(entry, entry_rel)
                node.children.append(child_node)

            return node

        return _build_tree(self.repo_path)

    def save_structure(self, tree: DirectoryNode) -> Path:
        """Save repository structure to structure.json (US-1.2)."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        structure_file = self.output_dir / "structure.json"
        
        # Convert DirectoryNode to dict
        data = tree.model_dump(exclude_none=True)
        structure_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Repository structure saved to {structure_file}")
        return structure_file

    def scan_and_parse(self) -> Tuple[DirectoryNode, List[FileIndex]]:
        """Run complete repository scan and parse all supported source files."""
        self.prepare_repository()
        tree = self.scan_structure()
        self.save_structure(tree)

        file_indexes: List[FileIndex] = []
        spec = self.load_gitignore()

        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES]
            
            for file in sorted(files):
                file_path = Path(root) / file
                ext = file_path.suffix.lower()

                if ext not in self.parsers:
                    continue

                rel_path = file_path.relative_to(self.repo_path).as_posix()
                if spec and spec.match_file(rel_path):
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                    parser = self.parsers[ext]
                    file_idx = parser.parse(
                        file_path=str(file_path),
                        content=content,
                        repo_path=str(self.repo_path),
                    )
                    file_indexes.append(file_idx)
                except Exception as e:
                    logger.error(f"Error parsing file '{rel_path}': {e}")

        return tree, file_indexes

    def cleanup(self):
        """Remove temporary directory if cloned from remote."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
