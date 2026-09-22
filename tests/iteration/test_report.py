import json

from tools.iteration.report import write_reports


def test_iteration_writes_machine_and_human_readable_reports(tmp_path) -> None:
    report = {
        "name": "test-iteration",
        "duration_ms": 12.5,
        "dataset": {"cities": 1, "drivers": 10, "reviews": 100},
        "workload": {"corrections": 10},
        "audit": {"passed": True, "checks": []},
    }
    json_path, md_path = write_reports(report, tmp_path)

    assert json.loads(json_path.read_text()) == report
    assert "Audit: **PASS**" in md_path.read_text()
    assert 'Workload: `{"corrections": 10}`' in md_path.read_text()
