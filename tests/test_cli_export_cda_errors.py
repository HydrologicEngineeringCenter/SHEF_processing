from click.testing import CliRunner


def test_export_cda_missing_required_args():
    from shef.shef_parser import cli

    runner = CliRunner()
    # omit --office
    result = runner.invoke(
        cli, ["export", "--api-root", "http://x", "--timeseries-group", "TG"]
    )
    # click should report missing required option
    assert result.exit_code != 0
    assert "Missing option" in result.output or "Error" in result.output
