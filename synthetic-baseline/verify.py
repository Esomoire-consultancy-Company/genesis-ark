"""Fixture-only CI contract. No live identity, network, payments or execution."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
WHITELIST = {"request_id", "actor_id", "action", "environment", "node_id", "legal_supplier_id"}
FORBIDDEN = {"password", "token", "secret", "email", "phone", "api_key", "private_key"}

def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def load():
    data = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
    if data.get("synthetic") is not True or data.get("environment") != "synthetic-ci" or data.get("fixture_id") != "GENESIS-SYNTHETIC-BASELINE-R01":
        raise ValueError("Synthetic fixture identity missing")
    def scan(v):
        if isinstance(v, dict):
            if set(v) & FORBIDDEN:
                raise ValueError("Sensitive field in fixture")
            for child in v.values(): scan(child)
        elif isinstance(v, list):
            for child in v: scan(child)
    scan(data)
    for field, key in (("actors","id"), ("organizations","id"), ("licences","id"), ("action_policies","action")):
        values = [row[key] for row in data[field]]
        if len(set(values)) != len(values): raise ValueError("Duplicate "+field)
    if len(data["actors"]) != 10: raise ValueError("Unexpected actor fixture count")
    if any(not a["id"].startswith("SYN-") for a in data["actors"]): raise ValueError("Non synthetic ID")
    if any(not lic.get("synthetic") or not lic["id"].startswith("SYN-LIC-") for lic in data["licences"]):
        raise ValueError("Non synthetic licence")
    return data

def decide(data, request):
    if set(request) - WHITELIST: raise ValueError("Unrecognised authority field")
    if request.get("environment", "synthetic-ci") != "synthetic-ci": return "DENY","ENVIRONMENT_DENIED"
    action = request.get("action", "")
    policy = next((x for x in data["action_policies"] if x["action"]==action), None)
    if not action.endswith(".synthetic") or policy is None: return "DENY","UNKNOWN_ACTION"
    actor = next((x for x in data["actors"] if x["id"]==request.get("actor_id")), None)
    if not actor: return "DENY","UNKNOWN_ACTOR"
    if actor["state"]!="ACTIVE": return "DENY","IDENTITY_INACTIVE"
    member = next((x for x in data["memberships"] if x["actor_id"]==actor["id"]), None)
    if member is None: return "DENY","COMMONS_MEMBERSHIP_REQUIRED"
    if member["state"]!="ACTIVE": return "DENY","COMMONS_MEMBERSHIP_INACTIVE"
    if actor["role"]!=policy["role"]: return "DENY","ROLE_DENIED"
    clock=dt(data["test_clock"])
    if policy["requires_representation"]:
        node=request.get("node_id")
        if not node: return "DENY","NODE_SCOPE_REQUIRED"
        reps=(x for x in data["representations"] if x["actor_id"]==actor["id"])
        if not any(x["node_id"]==node and x["state"]=="ACTIVE" and dt(x["valid_until"])>clock for x in reps):
            return "DENY","NODE_REPRESENTATION_DENIED"
        supplier=request.get("legal_supplier_id")
        if not supplier: return "DENY","LEGAL_SUPPLIER_REQUIRED"
        if not any(x["id"]==supplier and x["kind"]=="legal_supplier" for x in data["organizations"]):
            return "DENY","LEGAL_SUPPLIER_DENIED"
    licences=[x for x in data["licences"] if x["actor_id"]==actor["id"] and action in x["actions"]]
    if not licences: return "DENY","SYNTHETIC_LICENCE_MISSING"
    valid=[x for x in licences if x["state"]=="ACTIVE" and dt(x["valid_until"])>clock]
    if not valid: return "DENY","SYNTHETIC_LICENCE_EXPIRED_OR_INACTIVE"
    if policy["requires_representation"] and not any(
        x.get("node_id")==request["node_id"] and x.get("legal_supplier_id")==request["legal_supplier_id"]
        for x in valid
    ): return "DENY","LICENCE_SCOPE_MISMATCH"
    if policy["review_required"]: return "ESCALATE","SYNTHETIC_REVIEW_REQUIRED"
    return "ALLOW","SYNTHETIC_POLICY_ALLOW"

def verify():
    data=load()
    cases=json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))
    if len(cases)!=17: raise ValueError("Expected 17 fixture cases")
    for case in cases:
        actual=decide(data,case["request"])
        expected=(case["decision"],case["reason_code"])
        if actual!=expected: raise AssertionError((case["name"],actual,expected))
        print(f'{case["name"]}: {actual[0]} ({actual[1]})')
    try:
        decide(data, {"action":"creator.draft.synthetic","actor_id":"SYN-ACTOR-CREATOR-01","warden_decision":"ALLOW"})
        raise AssertionError("Authority injection was accepted")
    except ValueError:
        pass
    print("PASS: 17 synthetic scenarios; zero network operations or execution")
if __name__=="__main__":
    verify()
