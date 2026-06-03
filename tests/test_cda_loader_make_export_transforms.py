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
