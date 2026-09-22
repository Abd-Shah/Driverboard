import json
from pathlib import Path


def write_reports(report: dict[str, object], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    name = str(report["name"])
    json_path = output_dir / f"{name}.json"
    md_path = output_dir / f"{name}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n")
    dataset = report["dataset"]
    workload = report.get("workload", {})
    audit = report["audit"]
    markdown = f"""# {name}\n\n- Duration: {report["duration_ms"]} ms\n- Dataset: `{json.dumps(dataset)}`\n- Workload: `{json.dumps(workload)}`\n- Audit: **{"PASS" if audit["passed"] else "FAIL"}**\n\n```json\n{json.dumps(audit, indent=2)}\n```\n"""
    md_path.write_text(markdown)
    return json_path, md_path
