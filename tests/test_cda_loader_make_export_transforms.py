import types

from shef.loaders import cda_loader


def _fake_groups_response(assigned):
    return types.SimpleNamespace(
        json=[
            {
                "id": "GROUP_A",
                "description": "test group",
                "assigned-time-series": assigned,
            }
        ]
    )


def _make_loader():
    loader = cda_loader.CdaLoader(logger=None)
    loader._office_id = "OFF"
    loader._office_ids = ["OFF"]
    return loader


def test_make_export_transforms_skips_missing_alias_and_keeps_others(monkeypatch):
    """A time series missing the alias-id key must not abort the rest of the group."""
    assigned = [
        {"timeseries-id": "OFF.BadNoAlias.Flow.Inst.1Hour.0.Raw", "office-id": "OFF"},
        {
            "timeseries-id": "OFF.Good1.Flow.Inst.1Hour.0.Raw",
            "office-id": "OFF",
            "alias-id": "GOOD1.HG.RZ.1:Units=ft",
        },
    ]
    monkeypatch.setattr(
        cda_loader.cwms,
        "get_timeseries_groups",
        lambda **kw: _fake_groups_response(assigned),
    )

    loader = _make_loader()
    loader.make_export_transforms()

    assert loader._export_groups["GROUP_A"]["timeseries"] == [
        "OFF.Good1.Flow.Inst.1Hour.0.Raw"
    ]
    assert "OFF.Good1.Flow.Inst.1Hour.0.Raw" in loader._transforms


def test_make_export_transforms_skips_empty_alias_and_keeps_others(monkeypatch):
    """An empty alias-id string must not abort the rest of the group."""
    assigned = [
        {
            "timeseries-id": "OFF.BadEmpty.Flow.Inst.1Hour.0.Raw",
            "office-id": "OFF",
            "alias-id": "",
        },
        {
            "timeseries-id": "OFF.Good2.Flow.Inst.1Hour.0.Raw",
            "office-id": "OFF",
            "alias-id": "GOOD2.HG.RZ.1",
        },
    ]
    monkeypatch.setattr(
        cda_loader.cwms,
        "get_timeseries_groups",
        lambda **kw: _fake_groups_response(assigned),
    )

    loader = _make_loader()
    loader.make_export_transforms()

    assert loader._export_groups["GROUP_A"]["timeseries"] == [
        "OFF.Good2.Flow.Inst.1Hour.0.Raw"
    ]


def test_make_transforms_passes_office_filter_to_cwms(monkeypatch):
    """make_transforms() should pass the office filter through to cwms.get_timeseries_group."""
    calls = []

    def fake_get_group(**kwargs):
        calls.append(kwargs)
        return types.SimpleNamespace(
            json={
                "assigned-time-series": [
                    {
                        "timeseries-id": "MVP.Test.Flow.Inst.1Hour.0.Raw",
                        "office-id": "MVP",
                        "alias-id": "TEST.HG.RZ.1",
                    }
                ]
            }
        )

    monkeypatch.setattr(cda_loader.cwms, "get_timeseries_group", fake_get_group)

    loader = cda_loader.CdaLoader(logger=None)
    loader.make_transforms(office="MVP")

    assert len(calls) == 1
    assert calls[0]["office_id"] == "MVP"
    assert any(
        t.timeseries_id == "MVP.Test.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )


def test_transform_key_checks_all_requested_offices():
    """Multi-office lookups should not be biased to the first office in the list."""
    loader = cda_loader.CdaLoader(logger=None)
    loader._office_ids = ["LRL", "LRN"]
    loader._office_id = "LRL"
    loader._transforms = {
        "LRN.ALCT1.HGIRZZ": cda_loader.ShefTransform(
            office="LRN",
            location="ALCT1",
            parameter_code="HGIRZZ",
            timeseries_id="LRN.ALCT1.Flow.Inst.1Hour.0.Raw",
            units="ft",
            timezone=None,
            dl_time=None,
        )
    }

    loader._shef_value = types.SimpleNamespace(
        location="ALCT1",
        parameter_code="HGIRZZQ",
    )
    value = loader._shef_value
    assert loader.transform_key == "LRN.ALCT1.HGIRZZ"
    assert loader.get_time_series_name(value) == "LRN.ALCT1.Flow.Inst.1Hour.0.Raw"


def test_make_transforms_accepts_multiple_offices(monkeypatch):
    """make_transforms() should use a single unscoped API call and filter the response to the requested offices."""
    calls = []

    def fake_get_group(**kwargs):
        calls.append(kwargs)
        return types.SimpleNamespace(
            json={
                "assigned-time-series": [
                    {
                        "timeseries-id": "MVP.Multi.Flow.Inst.1Hour.0.Raw",
                        "office-id": "MVP",
                        "alias-id": "MULTIMVP.HG.RZ.1",
                    },
                    {
                        "timeseries-id": "LRL.Multi.Flow.Inst.1Hour.0.Raw",
                        "office-id": "LRL",
                        "alias-id": "MULTILRL.HG.RZ.1",
                    },
                    {
                        "timeseries-id": "SWG.Multi.Flow.Inst.1Hour.0.Raw",
                        "office-id": "SWG",
                        "alias-id": "MULTISWG.HG.RZ.1",
                    },
                ]
            }
        )

    monkeypatch.setattr(cda_loader.cwms, "get_timeseries_group", fake_get_group)

    loader = cda_loader.CdaLoader(logger=None)
    loader.make_transforms(office=["MVP", "LRL"])

    assert len(calls) == 1
    assert "office_id" not in calls[0]
    assert any(
        t.timeseries_id == "MVP.Multi.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )
    assert any(
        t.timeseries_id == "LRL.Multi.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )
    assert all(
        t.timeseries_id != "SWG.Multi.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )


def test_set_options_parses_multi_office_cli_string():
    """The command-line office option should parse into a list of office IDs."""
    loader = cda_loader.CdaLoader(logger=None)
    loader.set_options("[https://example.test/cwms-data/][abc123][\"MVP\",\"LRL\",\"SWG\"]")

    assert loader._cda_url == "https://example.test/cwms-data/"
    assert loader._office_ids == ["MVP", "LRL", "SWG"]
    assert loader._office_id == "MVP"


def test_set_options_parses_bracketed_multi_office_cli_string():
    """Bracketed comma-delimited office options should flatten into a clean office list."""
    loader = cda_loader.CdaLoader(logger=None)
    loader.set_options("[https://example.test/cwms-data/][abc123][[LRN,LRL]]")

    assert loader._cda_url == "https://example.test/cwms-data/"
    assert loader._office_ids == ["LRN", "LRL"]
    assert loader._office_id == "LRN"

    loader = cda_loader.CdaLoader(logger=None)
    loader.set_options("[https://example.test/cwms-data/][abc123][LRL,LRN]")
    assert loader._office_ids == ["LRL", "LRN"]
    assert loader._office_id == "LRL"


def test_make_transforms_filters_duplicate_alias_by_office(monkeypatch):
    """A duplicate alias in another office should not be processed when office scoping is active."""
    calls = []

    def fake_get_group(**kwargs):
        calls.append(kwargs)
        office = kwargs.get("office_id")
        assigned = [
            {
                "timeseries-id": f"{office}.Test.Flow.Inst.1Hour.0.Raw",
                "office-id": office,
                "alias-id": "TEST.HG.RZ.1",
            }
        ]
        if office == "LRL":
            assigned.append(
                {
                    "timeseries-id": "LRL.Other.Flow.Inst.1Hour.0.Raw",
                    "office-id": "LRL",
                    "alias-id": "TEST.HG.RZ.1",
                }
            )
        return types.SimpleNamespace(json={"assigned-time-series": assigned})

    monkeypatch.setattr(cda_loader.cwms, "get_timeseries_group", fake_get_group)

    loader = cda_loader.CdaLoader(logger=None)
    loader.make_transforms(office="MVP")

    assert len(calls) == 1
    assert calls[0]["office_id"] == "MVP"
    assert any(
        t.timeseries_id == "MVP.Test.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )
    assert all(
        t.timeseries_id != "LRL.Other.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )


def test_make_transforms_processes_each_office_in_list(monkeypatch):
    """When multiple offices are supplied, they should be filtered from one unscoped response."""
    calls = []

    def fake_get_group(**kwargs):
        calls.append(kwargs)
        return types.SimpleNamespace(
            json={
                "assigned-time-series": [
                    {
                        "timeseries-id": "MVP.List.Flow.Inst.1Hour.0.Raw",
                        "office-id": "MVP",
                        "alias-id": "LISTMVP.HG.RZ.1",
                    },
                    {
                        "timeseries-id": "LRL.List.Flow.Inst.1Hour.0.Raw",
                        "office-id": "LRL",
                        "alias-id": "LISTLRL.HG.RZ.1",
                    },
                ]
            }
        )

    monkeypatch.setattr(cda_loader.cwms, "get_timeseries_group", fake_get_group)

    loader = cda_loader.CdaLoader(logger=None)
    loader.make_transforms(office=["MVP", "LRL"])

    assert len(calls) == 1
    assert "office_id" not in calls[0]
    assert any(
        t.timeseries_id == "MVP.List.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )
    assert any(
        t.timeseries_id == "LRL.List.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )


def test_make_transforms_without_office_uses_default_unscoped_lookup(monkeypatch):
    """When no office is supplied, make_transforms should omit the office filter and use the default unscoped query."""
    calls = []

    def fake_get_group(**kwargs):
        calls.append(kwargs)
        return types.SimpleNamespace(
            json={
                "assigned-time-series": [
                    {
                        "timeseries-id": "DEFAULT.Test.Flow.Inst.1Hour.0.Raw",
                        "office-id": "MVP",
                        "alias-id": "TEST.HG.RZ.1",
                    }
                ]
            }
        )

    monkeypatch.setattr(cda_loader.cwms, "get_timeseries_group", fake_get_group)

    loader = cda_loader.CdaLoader(logger=None)
    loader._office_ids = []
    loader.make_transforms()

    assert len(calls) == 1
    assert "office_id" not in calls[0]
    assert any(
        t.timeseries_id == "DEFAULT.Test.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )


def test_get_matching_transforms_without_office_returns_all_office_matches():
    """Unscoped lookups should include all office-specific transforms for the same location and parameter."""
    loader = cda_loader.CdaLoader(logger=None)
    loader._office_ids = []
    loader._office_id = ""
    loader._transforms = {
        "LRL.ALCT1.HGIRZZ": cda_loader.ShefTransform(
            office="LRL",
            location="ALCT1",
            parameter_code="HGIRZZ",
            timeseries_id="LRL.ALCT1.Flow.Inst.1Hour.0.Raw",
            units="ft",
            timezone=None,
            dl_time=None,
        ),
        "LRN.ALCT1.HGIRZZ": cda_loader.ShefTransform(
            office="LRN",
            location="ALCT1",
            parameter_code="HGIRZZ",
            timeseries_id="LRN.ALCT1.Flow.Inst.1Hour.0.Raw",
            units="ft",
            timezone=None,
            dl_time=None,
        ),
    }

    loader._shef_value = types.SimpleNamespace(location="ALCT1", parameter_code="HGIRZZQ")
    matches = loader.get_matching_transforms(loader._shef_value)

    assert {m.office for m in matches} == {"LRL", "LRN"}
    assert {m.timeseries_id for m in matches} == {
        "LRL.ALCT1.Flow.Inst.1Hour.0.Raw",
        "LRN.ALCT1.Flow.Inst.1Hour.0.Raw",
    }


def test_make_transforms_keeps_unique_entries_when_same_alias_appears_in_multiple_offices(
    monkeypatch,
):
    """The transform map should keep separate office-specific entries from a single unscoped response."""
    calls = []

    def fake_get_group(**kwargs):
        calls.append(kwargs)
        return types.SimpleNamespace(
            json={
                "assigned-time-series": [
                    {
                        "timeseries-id": "MVP.SameAlias.Flow.Inst.1Hour.0.Raw",
                        "office-id": "MVP",
                        "alias-id": "SAME.HG.RZ.1",
                    },
                    {
                        "timeseries-id": "LRL.SameAlias.Flow.Inst.1Hour.0.Raw",
                        "office-id": "LRL",
                        "alias-id": "SAME.HG.RZ.1",
                    },
                ]
            }
        )

    monkeypatch.setattr(cda_loader.cwms, "get_timeseries_group", fake_get_group)

    loader = cda_loader.CdaLoader(logger=None)
    loader.make_transforms(office=["MVP", "LRL"])

    assert len(calls) == 1
    assert "office_id" not in calls[0]
    assert set(loader._transforms) == {"MVP.SAME.HGURZ", "LRL.SAME.HGURZ"}
    assert any(
        t.timeseries_id == "MVP.SameAlias.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )
    assert any(
        t.timeseries_id == "LRL.SameAlias.Flow.Inst.1Hour.0.Raw"
        for t in loader._transforms.values()
    )


def test_load_time_series_processes_all_matching_office_transforms(monkeypatch):
    """A single location+parameter should process every office-specific transform that matches."""
    loader = cda_loader.CdaLoader(logger=None)
    loader._office_ids = ["LRL", "LRN"]
    loader._office_id = "LRL"
    loader._transforms = {
        "LRL.ALCT1.HGIRZZ": cda_loader.ShefTransform(
            office="LRL",
            location="ALCT1",
            parameter_code="HGIRZZ",
            timeseries_id="LRL.ALCT1.Flow.Inst.1Hour.0.Raw",
            units="ft",
            timezone=None,
            dl_time=None,
        ),
        "LRN.ALCT1.HGIRZZ": cda_loader.ShefTransform(
            office="LRN",
            location="ALCT1",
            parameter_code="HGIRZZ",
            timeseries_id="LRN.ALCT1.Flow.Inst.1Hour.0.Raw",
            units="ft",
            timezone=None,
            dl_time=None,
        ),
    }
    loader._shef_value = types.SimpleNamespace(location="ALCT1", parameter_code="HGIRZZQ")
    loader._time_series = [["2024-01-01 00:00:00", "15.0"]]

    loader.load_time_series()

    assert {payload["name"] for payload in loader._payloads} == {
        "LRL.ALCT1.Flow.Inst.1Hour.0.Raw",
        "LRN.ALCT1.Flow.Inst.1Hour.0.Raw",
    }


def test_make_export_transforms_scopes_fetch_to_requested_group(monkeypatch):
    """When a group_id is given, only that group should be fetched from cwms (no warnings about other groups)."""
    calls = []

    def fake_get_groups(**kwargs):
        calls.append(kwargs)
        return _fake_groups_response(
            [
                {
                    "timeseries-id": "OFF.Only.Flow.Inst.1Hour.0.Raw",
                    "office-id": "OFF",
                    "alias-id": "ONLY.HG.RZ.1",
                }
            ]
        )

    monkeypatch.setattr(cda_loader.cwms, "get_timeseries_groups", fake_get_groups)

    loader = _make_loader()
    loader.make_export_transforms(group_id="GROUP_A")

    assert len(calls) == 1
    assert calls[0]["timeseries_group_like"] == "^GROUP_A$"
    assert calls[0]["group_office_id"] == "OFF"
    assert calls[0]["office_id"] == "OFF"
    assert "GROUP_A" in loader._loaded_export_group_ids
    assert loader._loaded_all_export_groups is False

    # second call for same group is a no-op (no extra fetch)
    loader.make_export_transforms(group_id="GROUP_A")
    assert len(calls) == 1


def test_get_office_summary_reports_time_series_and_values_by_office():
    """The loader summary should break totals down by office for the loaded payloads."""
    loader = cda_loader.CdaLoader(logger=None)
    loader._office_load_stats = {
        "MVP": {"time_series": 2, "value_count": 5},
        "LRL": {"time_series": 1, "value_count": 3},
    }

    assert loader.get_office_summary() == (
        "LRL: 1 time series, 3 values; MVP: 2 time series, 5 values"
    )


def test_load_time_series_tracks_blank_office_as_default():
    """A missing office should still report a valid office bucket instead of an empty label."""
    loader = cda_loader.CdaLoader(logger=None)
    loader._shef_value = types.SimpleNamespace(
        location="ALCT1",
        parameter_code="HGIRZZQ",
    )
    loader._time_series = [["2024-01-01 00:00:00", "15.0"]]
    loader._transforms = {
        "ALCT1.HGIRZZ": cda_loader.ShefTransform(
            office="",
            location="ALCT1",
            parameter_code="HGIRZZ",
            timeseries_id="ALCT1.Flow.Inst.1Hour.0.Raw",
            units="ft",
            timezone=None,
            dl_time=None,
        )
    }
    loader._office_id = ""

    loader.load_time_series()

    assert loader.get_office_summary() == "DEFAULT: 1 time series, 1 values"
    assert loader._payloads[0]["office-id"] == "DEFAULT"


def test_make_export_transforms_skips_malformed_alias_and_keeps_others(monkeypatch):
    """A malformed alias-id (raises inside make_shef_transform) must not abort the rest."""
    assigned = [
        {
            "timeseries-id": "OFF.BadMalformed.Flow.Inst.1Hour.0.Raw",
            "office-id": "OFF",
            "alias-id": "not-a-valid-shef-alias",
        },
        {
            "timeseries-id": "OFF.Good3.Flow.Inst.1Hour.0.Raw",
            "office-id": "OFF",
            "alias-id": "GOOD3.HG.RZ.1",
        },
    ]
    monkeypatch.setattr(
        cda_loader.cwms,
        "get_timeseries_groups",
        lambda **kw: _fake_groups_response(assigned),
    )

    loader = _make_loader()
    loader.make_export_transforms()

    assert "OFF.Good3.Flow.Inst.1Hour.0.Raw" in loader._export_groups["GROUP_A"][
        "timeseries"
    ]
