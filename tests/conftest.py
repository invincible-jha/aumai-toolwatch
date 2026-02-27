"""Shared test fixtures for aumai-toolwatch tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from aumai_toolwatch.core import ToolFingerprinter
from aumai_toolwatch.models import MutationAlert, ToolFingerprint, WatchConfig


# ---------------------------------------------------------------------------
# Schema fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def simple_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    }


@pytest.fixture()
def modified_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
            "offset": {"type": "integer"},  # new field added
        },
        "required": ["query"],
    }


@pytest.fixture()
def empty_schema() -> dict:
    return {}


# ---------------------------------------------------------------------------
# Sample response fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_responses() -> list[dict]:
    return [
        {"result": "found", "count": 10, "items": ["a", "b"]},
        {"result": "found", "count": 5, "items": ["c"]},
        {"result": "not_found", "count": 0, "items": []},
    ]


@pytest.fixture()
def modified_responses() -> list[dict]:
    return [
        {"result": "found", "count": 10, "items": ["a"], "metadata": {"source": "web"}},
    ]


@pytest.fixture()
def empty_responses() -> list[dict]:
    return []


# ---------------------------------------------------------------------------
# ToolFingerprint fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fingerprinter() -> ToolFingerprinter:
    return ToolFingerprinter()


@pytest.fixture()
def baseline_fingerprint(
    fingerprinter: ToolFingerprinter,
    simple_schema: dict,
    sample_responses: list[dict],
) -> ToolFingerprint:
    return fingerprinter.fingerprint(
        tool_name="search-tool",
        schema=simple_schema,
        sample_responses=sample_responses,
        version="1.0.0",
    )


@pytest.fixture()
def schema_changed_fingerprint(
    fingerprinter: ToolFingerprinter,
    modified_schema: dict,
    sample_responses: list[dict],
) -> ToolFingerprint:
    return fingerprinter.fingerprint(
        tool_name="search-tool",
        schema=modified_schema,
        sample_responses=sample_responses,
        version="1.1.0",
    )


@pytest.fixture()
def response_changed_fingerprint(
    fingerprinter: ToolFingerprinter,
    simple_schema: dict,
    modified_responses: list[dict],
) -> ToolFingerprint:
    return fingerprinter.fingerprint(
        tool_name="search-tool",
        schema=simple_schema,
        sample_responses=modified_responses,
        version="1.0.1",
    )


@pytest.fixture()
def both_changed_fingerprint(
    fingerprinter: ToolFingerprinter,
    modified_schema: dict,
    modified_responses: list[dict],
) -> ToolFingerprint:
    return fingerprinter.fingerprint(
        tool_name="search-tool",
        schema=modified_schema,
        sample_responses=modified_responses,
        version="2.0.0",
    )


# ---------------------------------------------------------------------------
# File fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def schema_file(tmp_path: Path, simple_schema: dict) -> Path:
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(simple_schema), encoding="utf-8")
    return path


@pytest.fixture()
def modified_schema_file(tmp_path: Path, modified_schema: dict) -> Path:
    path = tmp_path / "modified_schema.json"
    path.write_text(json.dumps(modified_schema), encoding="utf-8")
    return path
