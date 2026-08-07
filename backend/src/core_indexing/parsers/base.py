"""Abstract base class for language-specific AST parsers.

Each language parser (Java, C#) extends ``BaseLanguageParser`` and
implements the ``parse`` method that converts a source file into a
``FileIndex`` containing normalised ``ASTSymbolNode`` instances.

The driver-based architecture mirrors the design in
``docs/designs/ast-parser-design.md`` Section 2 (AST Subsystem Architecture):

    Source Code File Stream → Language Router → Parser Driver → Normaliser
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import List, Tuple

from core_indexing.models import FileIndex, Language


class BaseLanguageParser(ABC):
    """Contract that every language parser driver must satisfy."""

    @property
    @abstractmethod
    def language(self) -> Language:
        """The language this parser handles."""
        ...

    @property
    @abstractmethod
    def file_extensions(self) -> Tuple[str, ...]:
        """File extensions this parser handles (e.g. ``('.java',)``)."""
        ...

    @abstractmethod
    def parse(self, file_path: str, content: str, repo_path: str = "") -> FileIndex:
        """Parse a single source file and return a ``FileIndex``.

        Parameters
        ----------
        file_path:
            Absolute path to the source file.
        content:
            Raw text content of the source file.
        repo_path:
            Absolute path to the repository root, used for computing
            relative paths.

        Returns
        -------
        FileIndex
            Per-file metadata and extracted AST symbols.
        """
        ...

    # ------------------------------------------------------------------
    # Shared utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _relative_path(file_path: str, repo_path: str) -> str:
        """Compute a forward-slash relative path from *repo_path* to *file_path*."""
        import os

        if repo_path:
            try:
                rel = os.path.relpath(file_path, repo_path)
            except ValueError:
                rel = file_path
        else:
            rel = file_path
        return rel.replace("\\", "/")

    @staticmethod
    def _clean_javadoc(raw: str) -> str:
        """Strip ``/** … */`` markers and leading ``*`` from Javadoc text."""
        # Remove opening /** and closing */
        text = raw.strip()
        if text.startswith("/**"):
            text = text[3:]
        if text.endswith("*/"):
            text = text[:-2]
        # Remove leading * on each line
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("*"):
                stripped = stripped[1:].strip()
            lines.append(stripped)
        return "\n".join(lines).strip()

    @staticmethod
    def _clean_xml_doc(lines: List[str]) -> str:
        """Clean ``///`` XML doc-comment lines into plain text."""
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("///"):
                stripped = stripped[3:].strip()
            cleaned.append(stripped)
        return "\n".join(cleaned).strip()
