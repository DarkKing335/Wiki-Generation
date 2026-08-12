"""Integration tests for the RepoAtlas CLI pipeline."""

from __future__ import annotations

from pathlib import Path
import pytest

from cli import main, run_analysis_pipeline


def test_run_analysis_pipeline_no_llm(sample_repo_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_analysis_pipeline(str(sample_repo_dir), use_llm=False)

    indexes_dir = tmp_path / "indexes"
    analysis_dir = tmp_path / "analysis"
    graphs_dir = tmp_path / "graphs"

    assert (indexes_dir / "repository_index.json").exists()
    assert (indexes_dir / "structure_overview.json").exists()
    assert (indexes_dir / "structure.json").exists()

    assert (analysis_dir / "summaries.json").exists()
    assert (graphs_dir / "graph.json").exists()


def test_cli_invalid_path(capsys):
    with pytest.raises(SystemExit) as exc_info:
        run_analysis_pipeline("non_existent_directory_12345", use_llm=False)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "ERROR" in captured.out or "ERROR" in captured.err


def test_cli_main_argument_parsing(sample_repo_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main(["analyze", str(sample_repo_dir), "--no-llm"])

    assert (tmp_path / "indexes" / "repository_index.json").exists()
