import sys
import types

from click.testing import CliRunner


def test_export_cda_cli_wiring(tmp_path, monkeypatch):
    # collect instances created by the fake exporter
    instances = []

    class MockExporter:
        def __init__(self, api_root, office):
            self.api_root = api_root
            self.office = office
            self.start_time = None
            self.end_time = None
            self.output = None
            self.exported = None
            instances.append(self)

        def set_output(self, out):
            # keep reference to what was set as output
            self.output = out

        def export(self, timeseries_group):
            # record the argument passed to export()
            self.exported = timeseries_group

    # Insert a fake module into sys.modules so the lazy import inside the CLI finds it
    fake_mod = types.SimpleNamespace(CdaExporter=MockExporter)
    monkeypatch.setitem(sys.modules, "shef.exporters.cda_exporter", fake_mod)

    from shef.shef_parser import cli

    runner = CliRunner()
    outpath = tmp_path / "out.shef"
    result = runner.invoke(
        cli,
        [
            "export",
            "--api-root",
            "http://example.test/cda",
            "--office",
            "OFF",
            "--timeseries-group",
            "TG123",
            "--export-file",
            str(outpath),
        ],
    )

    # CLI should exit successfully
    assert result.exit_code == 0, result.output

    # One exporter instance should have been created and used
    assert len(instances) == 1
    inst = instances[0]
    assert inst.api_root == "http://example.test/cda"
    assert inst.office == "OFF"
    assert inst.exported == "TG123"
    # File output should have been set
    assert inst.output is not None
    # If a file object was used, ensure the file exists and is non-empty or zero-length is acceptable
    assert outpath.exists()
