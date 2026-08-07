"""Command-line entry point for the AI Analysis Engine (Epic 3).

Consumes the Core Indexing Engine's output and writes ``analysis/summaries.json``
for the Knowledge Graph builder (Epic 2) and the HTML Renderer (Epic 4)::

    python -m core_indexing <repo> -o indexes/     # Epic 1
    python -m ai_analysis indexes/ -o analysis/    # Epic 3, this tool
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from ai_analysis.chunker import Chunker
from ai_analysis.content import ContentGenerator
from ai_analysis.ir_models import load_repository_index, load_structure_overview
from ai_analysis.llm.base import LLMClient
from ai_analysis.llm.embeddings import EmbeddingClient
from ai_analysis.llm.null import NullLLMClient
from ai_analysis.llm.ollama import DEFAULT_ENDPOINT, DEFAULT_MODEL, OllamaClient
from ai_analysis.models import AnalysisResult, Tier
from ai_analysis.summarizer import Summarizer
from ai_analysis.taxonomy.provider import resolve_provider
from ai_analysis.tokens import DEFAULT_BUDGET
from ai_analysis.tools.definitions import build_registry
from ai_analysis.tools.dispatcher import ToolDispatcher

logger = logging.getLogger("ai_analysis")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ai_analysis",
        description=(
            "RepoAtlas AI Analysis Engine — hierarchical AST chunking and "
            "bottom-up summarization for local SLMs."
        ),
    )
    parser.add_argument(
        "index_dir",
        help="Directory containing repository_index.json (the output of core_indexing)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="analysis",
        help="Where to write summaries.json (default: analysis/)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model for summarization (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"Ollama server endpoint (default: {DEFAULT_ENDPOINT})",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Generate structural documentation without any model (US-3.2)",
    )
    parser.add_argument(
        "--taxonomy",
        choices=["auto", "index", "heuristic"],
        default="auto",
        help="Override taxonomy provider selection (default: auto)",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=DEFAULT_BUDGET,
        help=f"Maximum tokens per prompt (default: {DEFAULT_BUDGET})",
    )
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Disable lazy source loading via tool calls",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def build_llm(args: argparse.Namespace) -> LLMClient:
    """Select the summarization backend (ADR-006).

    Falls back to the null client when Ollama is unreachable, rather than
    failing: FR-9 requires documentation generation to proceed without an LLM.
    """
    if args.no_llm:
        logger.info("Running without an LLM; documentation will be structural only")
        return NullLLMClient()

    client = OllamaClient(model=args.model, endpoint=args.endpoint)
    if not client.health_check():
        logger.warning(
            "Ollama is not usable at %s with model '%s'; falling back to structural mode",
            args.endpoint, args.model,
        )
        client.close()
        return NullLLMClient()

    logger.info("Using Ollama model '%s' at %s", args.model, args.endpoint)
    return client


def run(args: argparse.Namespace) -> AnalysisResult:
    index = load_repository_index(args.index_dir)
    overview = load_structure_overview(args.index_dir)
    print(f"Loaded {len(index.symbols)} symbols from {index.repository_name}")

    force = None if args.taxonomy == "auto" else args.taxonomy
    provider = resolve_provider(overview, force=force)
    tree = provider.build(index, overview)

    print(
        f"Taxonomy ({provider.name}): "
        f"{len(tree.nodes_at(Tier.MODULE))} module(s), "
        f"{len(tree.nodes_at(Tier.CONTAINER))} container(s), "
        f"{len(tree.nodes_at(Tier.COMPONENT))} component(s), "
        f"{len(tree.nodes_at(Tier.CLASS))} class(es), "
        f"{len(tree.nodes_at(Tier.METHOD))} method(s)"
    )

    llm = build_llm(args)
    chunker = Chunker(index, tree)

    dispatcher: Optional[ToolDispatcher] = None
    if not args.no_tools and llm.enabled:
        embeddings = EmbeddingClient(endpoint=args.endpoint)
        registry = build_registry(chunker, embeddings=embeddings)
        dispatcher = ToolDispatcher(registry)

    summarizer = Summarizer(
        index, tree, llm,
        chunker=chunker,
        dispatcher=dispatcher,
        budget=args.budget,
    )

    print(f"Summarizing {len(tree.bottom_up())} nodes bottom-up...")
    summaries = summarizer.run()

    content = ContentGenerator(index, tree, summaries, llm=llm).generate_all()

    result = AnalysisResult(
        repository_name=index.repository_name,
        repository_path=index.repository_path,
        model=args.model if llm.enabled else None,
        llm_enabled=llm.enabled,
        taxonomy=tree,
        summaries=summaries,
        content=content,
        token_reports=summarizer.token_reports,
    )

    llm.close()
    return result


def write_result(result: AnalysisResult, output_dir: str) -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)

    output_file = path / "summaries.json"
    output_file.write_text(
        json.dumps(result.model_dump(mode="json", exclude_none=True), indent=2),
        encoding="utf-8",
    )
    return output_file


def report(result: AnalysisResult) -> None:
    """Print the acceptance numbers Epic 3 is measured against."""
    print(f"\nGenerated {len(result.summaries)} summaries")

    violations = result.budget_violations
    ceiling = result.token_reports[0].budget if result.token_reports else DEFAULT_BUDGET
    print(f"Max prompt: {result.max_prompt_tokens} tokens (budget {ceiling})")

    if violations:
        print(f"WARNING: {len(violations)} prompt(s) exceeded the budget:")
        for report_entry in violations[:5]:
            print(f"  - {report_entry.node_id}: {report_entry.estimated_tokens} tokens")
    else:
        print("All prompts within budget (US-3.5)")

    measured = [r for r in result.token_reports if r.actual_tokens is not None]
    if measured:
        worst = max(r.actual_tokens for r in measured)
        print(f"Ground truth from the model: max {worst} tokens over {len(measured)} prompt(s)")

    timings = [r.elapsed_seconds for r in result.token_reports if r.elapsed_seconds]
    if timings:
        print(f"Slowest node: {max(timings):.2f}s")


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        result = run(args)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - surface a clean message, not a traceback
        logger.debug("Analysis failed", exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_file = write_result(result, args.output_dir)
    report(result)
    print(f"\nSaved analysis to: {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
