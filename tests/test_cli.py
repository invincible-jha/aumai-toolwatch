"""Comprehensive CLI tests for aumai-toolwatch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from aumai_toolwatch.cli import main


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ===========================================================================
# --version
# ===========================================================================


class TestVersion:
    def test_version_exits_zero(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0

    def test_version_shows_version_string(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert "0.1.0" in result.output


# ===========================================================================
# --help
# ===========================================================================


class TestHelp:
    def test_main_help_exits_zero(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0

    @pytest.mark.parametrize("subcommand", ["baseline", "check", "alerts"])
    def test_subcommands_in_help(self, runner: CliRunner, subcommand: str) -> None:
        result = runner.invoke(main, ["--help"])
        assert subcommand in result.output

    def test_baseline_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["baseline", "--help"])
        assert result.exit_code == 0

    def test_check_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["check", "--help"])
        assert result.exit_code == 0

    def test_alerts_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["alerts", "--help"])
        assert result.exit_code == 0


# ===========================================================================
# baseline command
# ===========================================================================


class TestBaselineCommand:
    def test_baseline_exits_zero(self, runner: CliRunner, schema_file: Path, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main, ["baseline", "--tool", "my-tool", "--schema", str(schema_file)]
            )
            assert result.exit_code == 0

    def test_baseline_output_is_json(self, runner: CliRunner, schema_file: Path, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main, ["baseline", "--tool", "my-tool", "--schema", str(schema_file)]
            )
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "tool_name" in data

    def test_baseline_shows_tool_name(self, runner: CliRunner, schema_file: Path, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main, ["baseline", "--tool", "search-api", "--schema", str(schema_file)]
            )
            data = json.loads(result.output)
            assert data["tool_name"] == "search-api"

    def test_baseline_shows_schema_hash(self, runner: CliRunner, schema_file: Path, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main, ["baseline", "--tool", "tool", "--schema", str(schema_file)]
            )
            data = json.loads(result.output)
            assert len(data["schema_hash"]) == 64

    def test_baseline_shows_captured_at(self, runner: CliRunner, schema_file: Path, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main, ["baseline", "--tool", "tool", "--schema", str(schema_file)]
            )
            data = json.loads(result.output)
            assert "captured_at" in data

    def test_baseline_with_version(self, runner: CliRunner, schema_file: Path, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main,
                ["baseline", "--tool", "tool", "--schema", str(schema_file), "--version", "2.5.0"],
            )
            assert result.exit_code == 0

    def test_baseline_requires_tool(self, runner: CliRunner, schema_file: Path) -> None:
        result = runner.invoke(main, ["baseline", "--schema", str(schema_file)])
        assert result.exit_code != 0

    def test_baseline_requires_schema(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["baseline", "--tool", "tool"])
        assert result.exit_code != 0

    def test_baseline_missing_schema_file_exits_nonzero(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            main,
            ["baseline", "--tool", "tool", "--schema", str(tmp_path / "nonexistent.json")],
        )
        assert result.exit_code != 0

    def test_baseline_same_schema_same_hash(self, runner: CliRunner, schema_file: Path, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result1 = runner.invoke(
                main, ["baseline", "--tool", "tool", "--schema", str(schema_file)]
            )
            result2 = runner.invoke(
                main, ["baseline", "--tool", "tool", "--schema", str(schema_file)]
            )
            d1 = json.loads(result1.output)
            d2 = json.loads(result2.output)
            assert d1["schema_hash"] == d2["schema_hash"]

    def test_baseline_different_schema_different_hash(
        self, runner: CliRunner, schema_file: Path, modified_schema_file: Path, tmp_path: Path
    ) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result1 = runner.invoke(
                main, ["baseline", "--tool", "tool", "--schema", str(schema_file)]
            )
            result2 = runner.invoke(
                main, ["baseline", "--tool", "tool", "--schema", str(modified_schema_file)]
            )
            d1 = json.loads(result1.output)
            d2 = json.loads(result2.output)
            assert d1["schema_hash"] != d2["schema_hash"]


# ===========================================================================
# check command
# ===========================================================================


class TestCheckCommand:
    def test_check_no_mutation_after_same_schema(
        self, runner: CliRunner, schema_file: Path, tmp_path: Path
    ) -> None:
        import uuid
        unique_tool = f"test-tool-nomutation-{uuid.uuid4().hex[:8]}"
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Set baseline
            runner.invoke(
                main, ["baseline", "--tool", unique_tool, "--schema", str(schema_file)]
            )
            # Check with same schema
            result = runner.invoke(
                main, ["check", "--tool", unique_tool, "--schema", str(schema_file)]
            )
            assert result.exit_code == 0
            assert "No mutation" in result.output

    def test_check_mutation_detected(
        self, runner: CliRunner, schema_file: Path, modified_schema_file: Path, tmp_path: Path
    ) -> None:
        import uuid
        unique_tool = f"test-tool-mutation-{uuid.uuid4().hex[:8]}"
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(
                main, ["baseline", "--tool", unique_tool, "--schema", str(schema_file)]
            )
            result = runner.invoke(
                main, ["check", "--tool", unique_tool, "--schema", str(modified_schema_file)]
            )
            assert result.exit_code == 0
            # Output should be JSON with mutation info
            data = json.loads(result.output)
            assert "change_type" in data

    def test_check_no_prior_baseline_registers_baseline(
        self, runner: CliRunner, schema_file: Path, tmp_path: Path
    ) -> None:
        import uuid
        unique_tool = f"test-tool-newbaseline-{uuid.uuid4().hex[:8]}"
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(
                main, ["check", "--tool", unique_tool, "--schema", str(schema_file)]
            )
            assert result.exit_code == 0
            assert "No mutation" in result.output

    def test_check_requires_tool(self, runner: CliRunner, schema_file: Path) -> None:
        result = runner.invoke(main, ["check", "--schema", str(schema_file)])
        assert result.exit_code != 0

    def test_check_requires_schema(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["check", "--tool", "tool"])
        assert result.exit_code != 0

    def test_check_missing_schema_exits_nonzero(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(
            main, ["check", "--tool", "tool", "--schema", str(tmp_path / "missing.json")]
        )
        assert result.exit_code != 0


# ===========================================================================
# alerts command
# ===========================================================================


class TestAlertsCommand:
    def test_alerts_exits_zero(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["alerts"])
        assert result.exit_code == 0

    def test_alerts_output_is_string(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["alerts"])
        assert isinstance(result.output, str)

    def test_alerts_after_mutation_detected(
        self, runner: CliRunner, schema_file: Path, modified_schema_file: Path, tmp_path: Path
    ) -> None:
        import uuid
        unique_tool = f"test-tool-alerts-{uuid.uuid4().hex[:8]}"
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(
                main, ["baseline", "--tool", unique_tool, "--schema", str(schema_file)]
            )
            runner.invoke(
                main, ["check", "--tool", unique_tool, "--schema", str(modified_schema_file)]
            )
            result = runner.invoke(main, ["alerts"])
            assert result.exit_code == 0
