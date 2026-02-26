"""CLI entry point for aumai-toolwatch."""

from __future__ import annotations

import json
from pathlib import Path

import click

from aumai_toolwatch.core import ToolFingerprinter, WatchManager
from aumai_toolwatch.models import ToolFingerprint

# Persistent storage for baselines and alerts
_DEFAULT_STATE_DIR = Path.home() / ".aumai" / "toolwatch"


def _load_manager() -> WatchManager:
    """Load or initialise a WatchManager from disk."""
    manager = WatchManager()
    baselines_path = _DEFAULT_STATE_DIR / "baselines.json"
    if baselines_path.exists():
        raw = json.loads(baselines_path.read_text(encoding="utf-8"))
        for entry in raw:
            fp = ToolFingerprint.model_validate(entry)
            manager.add_baseline(fp)
    return manager


def _save_manager(manager: WatchManager) -> None:
    """Persist baselines to disk."""
    _DEFAULT_STATE_DIR.mkdir(parents=True, exist_ok=True)
    baselines_path = _DEFAULT_STATE_DIR / "baselines.json"
    data = [fp.model_dump(mode="json") for fp in manager.get_all_baselines()]
    baselines_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    alerts_path = _DEFAULT_STATE_DIR / "alerts.json"
    alerts_data = [a.model_dump(mode="json") for a in manager.get_alerts()]
    existing: list[dict[str, object]] = []
    if alerts_path.exists():
        existing = json.loads(alerts_path.read_text(encoding="utf-8"))
    existing.extend(alerts_data)
    alerts_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


@click.group()
@click.version_option()
def main() -> None:
    """AumAI Toolwatch — detect runtime changes in tool behaviour."""


@main.command("baseline")
@click.option("--tool", required=True, help="Name of the tool to baseline.")
@click.option(
    "--schema",
    "schema_file",
    required=True,
    type=click.Path(exists=True),
    help="Path to a JSON file containing the tool's schema.",
)
@click.option(
    "--version",
    "tool_version",
    default="unknown",
    show_default=True,
    help="Version string for the tool.",
)
def baseline_cmd(tool: str, schema_file: str, tool_version: str) -> None:
    """Capture and store a baseline fingerprint for a tool."""
    schema: dict[str, object] = json.loads(Path(schema_file).read_text(encoding="utf-8"))
    fingerprinter = ToolFingerprinter()
    fp = fingerprinter.fingerprint(tool, schema, [], version=tool_version)

    manager = _load_manager()
    manager.add_baseline(fp)
    _save_manager(manager)

    click.echo(
        json.dumps(
            {
                "tool_name": fp.tool_name,
                "schema_hash": fp.schema_hash,
                "response_pattern_hash": fp.response_pattern_hash,
                "captured_at": fp.captured_at.isoformat(),
            },
            indent=2,
        )
    )


@main.command("check")
@click.option("--tool", required=True, help="Name of the tool to check.")
@click.option(
    "--schema",
    "schema_file",
    required=True,
    type=click.Path(exists=True),
    help="Path to a JSON file containing the current tool schema.",
)
@click.option(
    "--version",
    "tool_version",
    default="unknown",
    show_default=True,
    help="Version string for the tool.",
)
def check_cmd(tool: str, schema_file: str, tool_version: str) -> None:
    """Check a tool against its stored baseline and report any mutations."""
    schema: dict[str, object] = json.loads(Path(schema_file).read_text(encoding="utf-8"))
    fingerprinter = ToolFingerprinter()
    current_fp = fingerprinter.fingerprint(tool, schema, [], version=tool_version)

    manager = _load_manager()
    alert = manager.check(tool, current_fp)
    _save_manager(manager)

    if alert is None:
        click.echo(f"No mutation detected for tool '{tool}'.")
    else:
        click.echo(
            json.dumps(
                {
                    "tool_name": alert.tool_name,
                    "change_type": alert.change_type,
                    "severity": alert.severity,
                    "detected_at": alert.detected_at.isoformat(),
                },
                indent=2,
            )
        )


@main.command("alerts")
def alerts_cmd() -> None:
    """List all recorded mutation alerts."""
    alerts_path = _DEFAULT_STATE_DIR / "alerts.json"
    if not alerts_path.exists():
        click.echo("No alerts recorded.")
        return

    raw: list[dict[str, object]] = json.loads(alerts_path.read_text(encoding="utf-8"))
    if not raw:
        click.echo("No alerts recorded.")
        return

    click.echo(json.dumps(raw, indent=2))


if __name__ == "__main__":
    main()
