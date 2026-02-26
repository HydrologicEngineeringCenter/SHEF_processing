import sys
import types

from click.testing import CliRunner


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
