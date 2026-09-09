import json

import pytest

from curie_audit_plane.adapters.completion import complete_stub
from curie_audit_plane.cli import main


def test_evaluate_writes_json_and_csv_report(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("curie_audit_plane.cli.completer_from_settings", lambda cfg=None: complete_stub)
    output_dir = tmp_path / "evaluation"

    assert main(["evaluate", "--output-dir", str(output_dir), "--encounters", "2", "--repetitions", "2"]) == 0

    report = json.loads((output_dir / "evaluation-report.json").read_text())
    csv_text = (output_dir / "evaluation-metrics.csv").read_text()
    assert report["schema_version"] == "curie-evaluation.v1.1"
    assert {metric["name"] for metric in report["metrics"]} >= {
        "audit_reconstruction_completeness",
        "field_presence_arc",
        "independently_verified_arc",
        "capture_overhead",
        "reviewer_task_success",
    }
    assert report["study"]["encounter_count"] == 2
    assert report["study"]["repetitions"] == 2
    assert report["study"]["observation_count"] == 4
    assert "cohort.audit_reconstruction_completeness" in csv_text
    assert "row_type,name,kind,status" in csv_text
    assert (output_dir / "evaluation-cohort-metrics.svg").read_text().startswith("<svg ")
    assert "Evaluation report:" in capsys.readouterr().out
    assert report["runtime"] == "deterministic-stub"


def test_evaluate_uses_settings_completer(tmp_path, monkeypatch):
    calls = {"count": 0}

    def counting_completer(request):
        calls["count"] += 1
        return complete_stub(request)

    monkeypatch.setattr("curie_audit_plane.cli.completer_from_settings", lambda cfg=None: counting_completer)
    assert main(["evaluate", "--output-dir", str(tmp_path / "evaluation"), "--encounters", "1", "--repetitions", "1"]) == 0
    assert calls["count"] >= 1


@pytest.mark.parametrize(
    ("option", "value"),
    [("--encounters", "0"), ("--encounters", "1001"), ("--repetitions", "0")],
)
def test_evaluate_rejects_out_of_range_counts(option, value, tmp_path):
    with pytest.raises(SystemExit):
        main(["evaluate", "--output-dir", str(tmp_path / "evaluation"), option, value])
