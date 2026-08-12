"""Command-line interface for Epic 2 graph generation and queries."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from knowledge_graph.builder import build_from_paths, load_graph, write_graph
from knowledge_graph.query import GraphQuery


def _kinds(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--kind",
        action="append",
        dest="kinds",
        help="Relationship kind to include; repeat to select multiple kinds",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m knowledge_graph",
        description="RepoAtlas Knowledge Graph Engine",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="Generate graph.json")
    build.add_argument("index", help="repository_index.json or its directory")
    build.add_argument("-a", "--analysis", help="Optional summaries.json or its directory")
    build.add_argument("-o", "--output-dir", default="graphs")

    query = commands.add_parser("query", help="Query neighboring relationships")
    query.add_argument("graph", help="graph.json or its directory")
    query.add_argument("node_id")
    query.add_argument(
        "--direction",
        choices=["outgoing", "incoming", "both"],
        default="both",
    )
    _kinds(query)

    dependencies = commands.add_parser("dependencies", help="Query outgoing dependencies")
    dependencies.add_argument("graph")
    dependencies.add_argument("node_id")
    _kinds(dependencies)

    dependents = commands.add_parser("dependents", help="Query incoming dependencies")
    dependents.add_argument("graph")
    dependents.add_argument("node_id")
    _kinds(dependents)

    path = commands.add_parser("path", help="Find a directed shortest path")
    path.add_argument("graph")
    path.add_argument("source")
    path.add_argument("target")
    _kinds(path)
    return parser


def _print_model(model) -> None:
    print(json.dumps(model.model_dump(mode="json", exclude_none=True), indent=2))


def run(args: argparse.Namespace) -> int:
    if args.command == "build":
        graph = build_from_paths(args.index, args.analysis)
        output = write_graph(graph, args.output_dir)
        print(output)
        return 0

    query = GraphQuery(load_graph(args.graph))
    if args.command == "query":
        result = query.query(args.node_id, args.direction, args.kinds)
    elif args.command == "dependencies":
        result = query.dependencies(args.node_id, args.kinds)
    elif args.command == "dependents":
        result = query.dependents(args.node_id, args.kinds)
    else:
        result = query.shortest_path(args.source, args.target, args.kinds)
    _print_model(result)
    return 0


def main(argv: Optional[list[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        raise SystemExit(run(args))
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
