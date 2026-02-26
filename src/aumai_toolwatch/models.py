"""Pydantic models for aumai-toolwatch."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

__all__ = [
    "ToolFingerprint",
    "MutationAlert",
    "WatchConfig",
]


class ToolFingerprint(BaseModel):
    """Stable fingerprint of a tool's schema and observed response patterns."""

    tool_name: str = Field(..., description="Unique name of the tool being fingerprinted")
    version: str = Field(..., description="Version string of the tool")
    schema_hash: str = Field(..., description="SHA-256 hex digest of the normalised tool schema")
    response_pattern_hash: str = Field(
        ...,
        description="SHA-256 hex digest of the aggregated sample response patterns",
    )
    captured_at: datetime = Field(..., description="UTC timestamp when this fingerprint was captured")


class MutationAlert(BaseModel):
    """Alert raised when a tool fingerprint changes from its baseline."""

    tool_name: str = Field(..., description="Name of the tool that mutated")
    change_type: str = Field(
        ...,
        description="Type of change detected: schema_change, behavior_change, or response_change",
    )
    old_fingerprint: ToolFingerprint = Field(..., description="Baseline fingerprint")
    new_fingerprint: ToolFingerprint = Field(..., description="Current fingerprint")
    detected_at: datetime = Field(..., description="UTC timestamp when the mutation was detected")
    severity: str = Field(
        ...,
        description="Severity level: low, medium, or high",
    )


class WatchConfig(BaseModel):
    """Configuration for the watch manager."""

    tools: list[str] = Field(default_factory=list, description="Tool names to monitor")
    check_interval_seconds: int = Field(
        default=300, description="How often to re-fingerprint tools"
    )
    alert_on: list[str] = Field(
        default_factory=lambda: ["schema_change", "behavior_change", "response_change"],
        description="Change types that should generate alerts",
    )
