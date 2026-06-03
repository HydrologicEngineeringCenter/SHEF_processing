"""Tests for the time-window parsing inside run_export (replaces former hec dependency)."""
import sys
import types
from datetime import datetime, timedelta

import click
import pytest
from click.testing import CliRunner


def _install_stub_cda_exporter(monkeypatch):
    captured = {}

    class MockExporter:
        def __init__(self, api_root, office):
            captured["api_root"] = api_root
            captured["office"] = office
            self.start_time = None
            self.end_time = None

        def set_output(self, out):
            pass

        def export(self, ts_or_group):
            captured["start_time"] = self.start_time
            captured["end_time"] = self.end_time
            captured["target"] = ts_or_group

    fake_mod = types.SimpleNamespace(CdaExporter=MockExporter)
    monkeypatch.setitem(sys.modules, "shef.exporters.cda_exporter", fake_mod)
    return captured


def _invoke(args):
    from shef.shef_parser import cli

    return CliRunner().invoke(cli, args)


def test_iso_start_and_end_parse_to_datetimes(monkeypatch, tmp_path):
    captured = _install_stub_cda_exporter(monkeypatch)
    result = _invoke(
        [
            "export",
            "--api-root",
            "http://x",
            "--office",
            "OFF",
            "--timeseries-group",
            "TG",
            "--start-time",
            "2024-01-15T06:00:00",
            "--end-time",
            "2024-01-16T06:00:00",
            "--export-file",
            str(tmp_path / "out.shef"),
        ]
    )
    assert result.exit_code == 0, result.output
    assert captured["start_time"] == datetime(2024, 1, 15, 6, 0, 0)
    assert captured["end_time"] == datetime(2024, 1, 16, 6, 0, 0)


def test_iso_date_only_parses_as_midnight(monkeypatch, tmp_path):
    captured = _install_stub_cda_exporter(monkeypatch)
    result = _invoke(
        [
            "export",
            "--api-root",
            "http://x",
            "--office",
            "OFF",
            "--timeseries-group",
            "TG",
            "--start-time",
            "2024-01-15",
            "--end-time",
            "2024-01-16",
            "--export-file",
            str(tmp_path / "out.shef"),
        ]
    )
    assert result.exit_code == 0, result.output
    assert captured["start_time"] == datetime(2024, 1, 15, 0, 0, 0)
    assert captured["end_time"] == datetime(2024, 1, 16, 0, 0, 0)


def test_relative_T_minus_1D_and_T(monkeypatch, tmp_path):
    captured = _install_stub_cda_exporter(monkeypatch)
    result = _invoke(
        [
            "export",
            "--api-root",
            "http://x",
            "--office",
            "OFF",
            "--timeseries-group",
            "GRFT",
            "--start-time",
            "T-1D",
            "--end-time",
            "T",
            "--export-file",
            str(tmp_path / "out.shef"),
        ]
    )
    assert result.exit_code == 0, result.output
    assert captured["end_time"] - captured["start_time"] == timedelta(days=1)


def test_invalid_time_string_reports_bad_parameter(monkeypatch, tmp_path):
    _install_stub_cda_exporter(monkeypatch)
    result = _invoke(
        [
            "export",
            "--api-root",
            "http://x",
            "--office",
            "OFF",
            "--timeseries-group",
            "TG",
            "--start-time",
            "not-a-time",
            "--end-time",
            "T",
        ]
    )
    assert result.exit_code != 0
    assert "Could not parse time" in result.output or "not-a-time" in result.output


def test_end_before_start_reports_bad_parameter(monkeypatch, tmp_path):
    _install_stub_cda_exporter(monkeypatch)
    result = _invoke(
        [
            "export",
            "--api-root",
            "http://x",
            "--office",
            "OFF",
            "--timeseries-group",
            "TG",
            "--start-time",
            "2024-01-16",
            "--end-time",
            "2024-01-15",
        ]
    )
    assert result.exit_code != 0
    assert "before start" in result.output or "Invalid time window" in result.output
