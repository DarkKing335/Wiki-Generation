"""Command-line interface entry point for the Core Indexing Engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core_indexing.indexer import RepositoryIndexer
from core_indexing.ir_generator import IRGenerator
from core_indexing.scanner import RepositoryScanner


def main():
    parser = argparse.ArgumentParser(
        description="RepoAtlas Core Indexing Engine — Source scanner for Java and C# repositories"
    )
    parser.add_argument(
        "target",
        help="Local repository directory path or Git URL",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="indexes",
        help="Output directory for generated IR files (default: indexes/)",
    )
    args = parser.parse_args()

    try:
        scanner = RepositoryScanner(target=args.target, output_dir=args.output_dir)
        print(f"Scanning repository: {args.target}...")

        tree, file_indexes = scanner.scan_and_parse()
        print(f"Scanned {len(file_indexes)} Java/C# source files.")

        indexer = RepositoryIndexer(
            repository_name=Path(scanner.repo_path).name,
            repository_path=str(scanner.repo_path),
            directory_tree=tree,
            file_indexes=file_indexes,
        )
        index = indexer.build_index()
        print(f"Extracted {len(index.symbols)} AST symbols and {len(index.relationships)} relationship edges.")

        generator = IRGenerator(index=index, output_dir=args.output_dir)
        repo_path, overview_path = generator.generate_all()

        print(f"Saved structure to: {args.output_dir}/structure.json")
        print(f"Saved IR to:        {repo_path}")
        print(f"Saved overview to:  {overview_path}")
        print("Indexing completed successfully!")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if 'scanner' in locals():
            scanner.cleanup()


if __name__ == "__main__":
    main()
