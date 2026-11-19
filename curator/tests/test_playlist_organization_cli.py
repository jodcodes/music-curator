import json
import os
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def organization_cli(monkeypatch):
    import main

    plan = {"version": 1, "kind": "organization", "fingerprint": "fixture", "operations": []}
    calls = {"constructed": 0, "preview": [], "apply": [], "classifiers": []}

    class Manager:
        def __init__(self):
            calls["constructed"] += 1

        def preview_playlist_organization(self, ids, classifier):
            calls["preview"].append(list(ids))
            return plan

        def apply_playlist_organization(self, reviewed, confirmed=False):
            calls["apply"].append((reviewed, confirmed))
            return {"success": True, "applied": 0, "failed": 0, "skipped": 0, "results": []}

    class Classifier:
        def __init__(self, **options):
            calls["classifiers"].append(options)

    monkeypatch.setitem(sys.modules, "src.playlist_manager", SimpleNamespace(PlaylistManager=Manager))
    monkeypatch.setitem(sys.modules, "src.playlist_classifier", SimpleNamespace(PlaylistClassifier=Classifier))
    monkeypatch.setattr(main, "require_macos", lambda feature: True)
    return main, calls, plan


@pytest.mark.parametrize("arguments", [[], ["--apply"], ["--yes"], ["--plan", "x"],
    ["--apply", "--plan", "x"], ["--apply", "--yes", "--plan", "x", "--playlist-id", "0123456789ABCDEF"]])
def test_organization_invalid_modes_do_not_construct_services(organization_cli, arguments):
    main, calls, _ = organization_cli
    assert main.main(["organize", *arguments]) == 1
    assert calls["constructed"] == 0
    assert calls["classifiers"] == []


def test_organization_preview_saves_exact_private_plan(organization_cli, tmp_path):
    main, calls, plan = organization_cli
    output = tmp_path / "review.json"
    assert main.main(["organize", "--playlist-id", "0123456789ABCDEF", "--save-plan", str(output)]) == 0
    assert json.loads(output.read_text()) == plan
    assert os.stat(output).st_mode & 0o777 == 0o600
    assert calls["preview"] == [["0123456789ABCDEF"]]
    assert calls["apply"] == []
    assert calls["classifiers"][0]["enable_genre_enrichment"] is False
    before = output.read_bytes()
    assert main.main(["organize", "--playlist-id", "0123456789ABCDEF", "--save-plan", str(output)]) == 1
    assert output.read_bytes() == before


def test_organization_apply_uses_saved_plan_without_classification(organization_cli, tmp_path):
    main, calls, plan = organization_cli
    output = tmp_path / "review.json"
    output.write_text(json.dumps(plan))
    assert main.main(["organize", "--plan", str(output), "--apply", "--yes"]) == 0
    assert calls["apply"] == [(plan, True)]
    assert calls["preview"] == []
    assert calls["classifiers"] == []
