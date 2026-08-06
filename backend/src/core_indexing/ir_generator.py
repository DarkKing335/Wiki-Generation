"""IR Generator — Serializes standard Intermediate Representation files.

Outputs:
- indexes/repository_index.json — Consolidated IR consumed by Member 2 (Knowledge Graph).
- indexes/structure_overview.json — 6-tier skeleton taxonomy consumed by Hierarchical Chunker.

Reference:
- docs/designs/ast-parser-design.md (Section 3: Binary & Compact Structural AST Serialization)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core_indexing.models import (
    ASTSymbolNode,
    DirectoryNode,
    RepositoryIndex,
    SymbolKind,
)

logger = logging.getLogger(__name__)


class IRGenerator:
    """Generates standardized IR JSON files for downstream pipeline modules."""

    def __init__(self, index: RepositoryIndex, output_dir: Optional[str] = None):
        self.index = index
        self.output_dir = Path(output_dir) if output_dir else Path("indexes")

    def generate_all(self) -> Tuple[Path, Path]:
        """Generate both repository_index.json and structure_overview.json."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        repo_index_path = self.generate_repository_index()
        overview_path = self.generate_structure_overview()

        return repo_index_path, overview_path

    def generate_repository_index(self) -> Path:
        """Serialize complete RepositoryIndex to repository_index.json."""
        output_file = self.output_dir / "repository_index.json"
        data = self.index.model_dump(mode="json", exclude_none=True)

        output_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Repository index saved to {output_file}")
        return output_file

    def generate_structure_overview(self) -> Path:
        """Generate compact 6-tier taxonomy skeleton structure_overview.json."""
        output_file = self.output_dir / "structure_overview.json"

        # Organize symbols by file/container
        overview_data = {
            "repository": self.index.repository_name,
            "languages": [l.value for l in self.index.languages],
            "total_symbols": len(self.index.symbols),
            "modules": self._build_skeleton_modules(),
        }

        output_file.write_text(json.dumps(overview_data, indent=2), encoding="utf-8")
        logger.info(f"Structure overview skeleton saved to {output_file}")
        return output_file

    def _build_skeleton_modules(self) -> List[Dict[str, Any]]:
        """Build compact 6-tier structural overview hierarchy."""
        # Group symbols by package/namespace (component tier)
        components: Dict[str, List[ASTSymbolNode]] = {}
        for sym in self.index.symbols:
            # Container package / namespace
            pkg = sym.symbol_id.rsplit(".", 1)[0] if "." in sym.symbol_id else "global"
            if pkg not in components:
                components[pkg] = []
            components[pkg].append(sym)

        component_list = []
        for pkg, syms in components.items():
            classes_info = []
            class_syms = [s for s in syms if s.kind in (
                SymbolKind.CLASS, SymbolKind.INTERFACE, SymbolKind.ENUM,
                SymbolKind.RECORD, SymbolKind.STRUCT,
            )]

            for cls in class_syms:
                methods = [
                    s.name for s in syms
                    if s.parent_symbol_id == cls.symbol_id and s.kind in (SymbolKind.METHOD, SymbolKind.CONSTRUCTOR)
                ]
                classes_info.append({
                    "fqn": cls.fully_qualified_name,
                    "kind": cls.kind.value,
                    "methods": methods,
                })

            if classes_info:
                component_list.append({
                    "name": pkg,
                    "classes": classes_info,
                })

        return [{
            "name": self.index.repository_name,
            "containers": [{
                "name": "MainContainer",
                "components": component_list,
            }]
        }]
