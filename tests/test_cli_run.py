from click.testing import CliRunner


def test_run_cli_calls_parse(monkeypatch):
    # Replace the real parse() with a lightweight fake that records kwargs
    recorded = {}

    def fake_parse(**kwargs):
        recorded.update(kwargs)

    monkeypatch.setattr("shef.shef_parser.parse", fake_parse)

    from shef.shef_parser import cli

    runner = CliRunner()
    result = runner.invoke(
        cli, ["parse", "--shefparm", "SHEFPARM", "--out", "outfile.txt"]
    )

    assert result.exit_code == 0, result.output
    assert "shefparm" in recorded
    assert recorded["shefparm"] == "SHEFPARM"
    assert "output_name" in recorded
    assert recorded["output_name"] == "outfile.txt"
