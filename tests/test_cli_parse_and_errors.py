import sys
import types

from click.testing import CliRunner


def test_base_delegates_to_run(monkeypatch):
    """When invoking the base CLI with no subcommand, it should delegate to `run` (parse implementation)."""
    called = {}

    def fake_run():
        called["ok"] = True

    # Patch the run implementation to a simple spy
    import shef.shef_parser as sp

    monkeypatch.setattr(sp, "parse", fake_run)

    runner = CliRunner()
    result = runner.invoke(sp.cli, [])
    assert result.exit_code == 0
    assert called.get("ok") is True


def test_parse_subcommand_version_prints_package(monkeypatch):
    """`parse --version` should print package/version information and exit 0."""
    import shef.shef_parser as sp

    runner = CliRunner()
    result = runner.invoke(sp.cli, ["parse", "--version"])
    assert result.exit_code == 0
    assert "Package" in result.output


def test_export_cda_missing_required_args_shows_error():
    """Calling `export cda` without required options should fail with Click missing option error."""
    import shef.shef_parser as sp

    runner = CliRunner()
    result = runner.invoke(sp.cli, ["export"])
    # Click should error when required options are missing
    assert result.exit_code != 0
    assert "Error" in result.output or "Missing option" in result.output
