"""Shared test fixtures for the Core Indexing Engine test suite."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
JAVA_FIXTURES_DIR = FIXTURES_DIR / "java"
CSHARP_FIXTURES_DIR = FIXTURES_DIR / "csharp"


@pytest.fixture
def java_fixtures_dir() -> Path:
    return JAVA_FIXTURES_DIR


@pytest.fixture
def csharp_fixtures_dir() -> Path:
    return CSHARP_FIXTURES_DIR


def read_fixture(path: Path) -> str:
    """Read a fixture file and return its content."""
    return path.read_text(encoding="utf-8")
