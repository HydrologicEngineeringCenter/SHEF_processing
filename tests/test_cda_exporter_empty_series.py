"""Regression tests for issue #75: export must not fail when some time series in a group are empty."""
import json
import types
from io import StringIO

import pytest

from shef.exporters import cda_exporter as cda_exporter_mod
from shef.loaders import cda_loader as cda_loader_mod


class _FakeResponse:
    def __init__(self, payload):
        self.json = payload


def _build_exporter(monkeypatch, tsids, response_for):
    """Construct a CdaExporter wired to canned cwms responses."""
    monkeypatch.setattr(cda_loader_mod.cwms, "init_session", lambda **kw: None)

    # stub the group-fetching call so make_export_transforms returns our tsids
    def fake_groups(**kw):
        return types.SimpleNamespace(
            json=[
                {
                    "id": "TG",
                    "description": "",
                    "assigned-time-series": [
                        {
                            "timeseries-id": tsid,
                            "office-id": "OFF",
                            "alias-id": f"LOC{i}.HG.RZ.1:Units=ft",
                        }
                        for i, tsid in enumerate(tsids)
                    ],
                }
            ]
        )

    monkeypatch.setattr(cda_loader_mod.cwms, "get_timeseries_groups", fake_groups)

    captured_unload = {}

    def fake_get_timeseries(**kw):
        return response_for(kw["ts_id"])

    monkeypatch.setattr(cda_exporter_mod.cwms, "get_timeseries", fake_get_timeseries)

    exporter = cda_exporter_mod.CdaExporter("http://x", "OFF")

    # capture what gets fed to the loader's unload step (parsed back from JSON)
    def fake_unload():
        raw = exporter._cda_loader._input.read()
        captured_unload["raw"] = raw
        captured_unload["parsed"] = json.loads(raw)

    exporter._cda_loader.unload = fake_unload
    exporter.set_output(StringIO())
    return exporter, captured_unload


def test_export_skips_empty_time_series_and_still_produces_valid_json(monkeypatch):
    tsids = [
        "OFF.LOC0.Flow.Inst.1Hour.0.Raw",
        "OFF.LOC1.Flow.Inst.1Hour.0.Raw",
        "OFF.LOC2.Flow.Inst.1Hour.0.Raw",
    ]

    def response_for(tsid):
        if tsid.endswith("LOC1.Flow.Inst.1Hour.0.Raw"):
            return _FakeResponse(
                {"name": tsid, "office-id": "OFF", "units": "ft", "values": []}
            )
        return _FakeResponse(
            {
                "name": tsid,
                "office-id": "OFF",
                "units": "ft",
                "values": [[0, 1.0, 0]],
            }
        )

    exporter, captured = _build_exporter(monkeypatch, tsids, response_for)
    exporter.export("TG")

    # JSON must be valid (regression for the column-118899 decode failure)
    assert "parsed" in captured, "unload was not invoked"
    payloads = captured["parsed"]
    assert isinstance(payloads, list)
    # the empty LOC1 series must be omitted, the other two kept
    names = [p["name"] for p in payloads]
    assert tsids[0] in names
    assert tsids[2] in names
    assert tsids[1] not in names


def test_export_handles_missing_values_key(monkeypatch):
    tsids = ["OFF.LOC0.Flow.Inst.1Hour.0.Raw"]

    def response_for(tsid):
        return _FakeResponse({"name": tsid, "office-id": "OFF"})

    exporter, captured = _build_exporter(monkeypatch, tsids, response_for)
    exporter.export("TG")
    # no values means unload is never invoked, and the build did not crash
    assert "parsed" not in captured


def test_export_handles_cwms_exception_per_series(monkeypatch):
    tsids = [
        "OFF.LOC0.Flow.Inst.1Hour.0.Raw",
        "OFF.LOC1.Flow.Inst.1Hour.0.Raw",
    ]

    def response_for(tsid):
        if "LOC0" in tsid:
            raise RuntimeError("simulated CDA outage for LOC0")
        return _FakeResponse(
            {"name": tsid, "office-id": "OFF", "units": "ft", "values": [[0, 1.0, 0]]}
        )

    exporter, captured = _build_exporter(monkeypatch, tsids, response_for)
    exporter.export("TG")

    parsed = captured["parsed"]
    assert len(parsed) == 1
    assert parsed[0]["name"] == tsids[1]
