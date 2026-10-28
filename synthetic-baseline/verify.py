"""Standard-library CI entry point for the fixed synthetic acceptance matrix."""
from pathlib import Path
import json
from engine import SyntheticOracle, load_manifest
from fixture_lock import verify_lock

ROOT = Path(__file__).resolve().parent


def run() -> list[dict]:
    verify_lock()
    oracle = SyntheticOracle(load_manifest())
    cases = json.loads((ROOT / "scenarios.json").read_text(encoding="utf-8"))
    results = []
    for index, case in enumerate(cases, 1):
        request = dict(case["request"])
        request["request_id"] = f"SYN-REQ-{index:03d}"
        request.setdefault("environment", "synthetic-ci")
        receipt = oracle.evaluate(request)
        assert receipt["decision"] == case["decision"], (case["name"], receipt)
        assert receipt["reason_code"] == case["reason_code"], (case["name"], receipt)
        assert receipt["synthetic"] is True and receipt["executable"] is False
        results.append({"scenario": case["name"], "decision": receipt["decision"],
                        "reason_code": receipt["reason_code"],
                        "evidence_sha256": receipt["evidence_sha256"]})
    assert oracle.effects == 0, "external effects should always be zero"
    return results


if __name__ == "__main__":
    results = run()
    print(f"PASS: {len(results)} synthetic authorization scenarios; zero external effects")
    for row in results:
        print(f"  {row['scenario']}: {row['decision']} ({row['reason_code']})")
