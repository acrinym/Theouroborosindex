from __future__ import annotations

import json
from pathlib import Path

import pytest

from ouroboros.data_journey import DataJourneyError, select_data_symbol, trace_data_journey
from ouroboros.data_journey_cli import main as data_main
from ouroboros.surface_scan import scan_surface_graph


SOURCE = '''
class Record:
    def normalize(self):
        return self

    def save(self):
        return None

    def emit(self):
        return None

    def helper(self):
        return None


def create_record():
    return Record()


def normalize_record(record):
    return Record.normalize(record)


def persist_record(record):
    return Record.save(record)


def emit_record(record):
    return Record.emit(record)


def dynamic_save(record):
    return record.save()
'''


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "app.py").write_text(SOURCE, encoding="utf-8")
    (root / "must_not_run.py").write_text("raise RuntimeError('target code executed')\n", encoding="utf-8")
    return root


def test_data_journey_groups_only_exact_lifecycle_calls(tmp_path: Path):
    root = _repo(tmp_path)
    _scanned, graph = scan_surface_graph(root, use_repo_config=False)
    selected = select_data_symbol(graph, "Record")
    analysis = trace_data_journey(selected, graph)

    assert analysis.data_symbol.qualified_name == "Record"
    assert analysis.stage_counts == {
        "created": 1,
        "transformed": 1,
        "persisted": 1,
        "emitted": 1,
    }
    assert [event.source.name for event in analysis.events] == [
        "create_record",
        "normalize_record",
        "persist_record",
        "emit_record",
    ]
    assert all(event.relationship == "calls" for event in analysis.events)
    assert all(event.trust.startswith("exact-") for event in analysis.events)
    assert "dynamic_save" not in {event.source.name for event in analysis.events}

    boundary_roles = {(boundary.member.name, boundary.role) for boundary in analysis.boundaries}
    assert ("normalize", "transformed") in boundary_roles
    assert ("save", "persisted") in boundary_roles
    assert ("emit", "emitted") in boundary_roles
    assert all(boundary.member.name != "helper" for boundary in analysis.boundaries)


def test_data_selector_refuses_ambiguous_short_names(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("class Record:\n    pass\n", encoding="utf-8")
    (root / "b.py").write_text("class Record:\n    pass\n", encoding="utf-8")
    _scanned, graph = scan_surface_graph(root, use_repo_config=False)

    with pytest.raises(DataJourneyError, match="ambiguous"):
        select_data_symbol(graph, "Record")


def test_data_journey_cli_writes_json_and_self_contained_report(tmp_path: Path):
    root = _repo(tmp_path)
    json_path = tmp_path / "journey.json"
    report_path = tmp_path / "journey.html"

    rc = data_main([
        str(root),
        "--data", "Record",
        "--json", str(json_path),
        "--report", str(report_path),
        "--canonical",
        "--quiet",
    ])

    assert rc == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema"] == {"name": "ouroboros-data-journey", "version": 1}
    assert payload["scan"]["target_execution"] is False
    assert payload["scan"]["event_requirement"] == "EXACT CALLS only"
    assert payload["data_journey"]["stage_counts"]["persisted"] == 1

    html = report_path.read_text(encoding="utf-8")
    assert "Ouroboros Data Journey" in html
    assert "Record" in html
    assert "Persisted" in html
    assert "runtime chronology" in html
