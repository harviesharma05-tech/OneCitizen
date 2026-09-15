"""
Fraud & leakage detection.

Entity resolution tells you who is who. This module asks the follow-up
question: given that, what looks wrong?
"""
from collections import defaultdict


def duplicate_applications(golden):
    """Same citizen, same scheme, more than once — requirement (ii)."""
    findings = []
    for g in golden:
        seen = defaultdict(list)
        for s in g["schemes"]:
            seen[s["scheme"]].append(s)
        for scheme, entries in seen.items():
            if len(entries) > 1:
                approved = [e for e in entries if e["status"] == "approved"]
                findings.append({
                    "citizen_id": g["citizen_id"],
                    "name": g["name_raw"],
                    "scheme": scheme,
                    "application_count": len(entries),
                    "approved_count": len(approved),
                    "duplicate_amount": sum(e["amount"] for e in approved[1:]),
                    "record_ids": [e["source_record_id"] for e in entries],
                    "severity": "high" if len(approved) > 1 else "medium",
                })
    findings.sort(key=lambda f: (-f["duplicate_amount"], -f["application_count"]))
    return findings


def shared_identifier_rings(golden):
    """Distinct citizens sharing a bank account or mobile number.

    One account funding several 'different' people is the classic
    ghost-beneficiary pattern.
    """
    rings = []
    for field, label in (("bank_account", "bank account"), ("phone", "mobile number")):
        groups = defaultdict(list)
        for g in golden:
            if g.get(field):
                groups[g[field]].append(g)
        for value, members in groups.items():
            if len(members) > 1:
                rings.append({
                    "identifier_type": label,
                    "identifier": value[:4] + "****" + value[-3:],
                    "citizen_count": len(members),
                    "citizens": [{"citizen_id": m["citizen_id"], "name": m["name_raw"]}
                                 for m in members],
                    "total_disbursed": sum(m["total_benefit"] for m in members),
                    "severity": "high" if len(members) > 2 else "medium",
                })
    rings.sort(key=lambda r: -r["total_disbursed"])
    return rings


def risk_score(profile, dup_index, ring_index):
    """0-100 risk score for one citizen, with the reasons that produced it."""
    score, reasons = 0, []

    dups = dup_index.get(profile["citizen_id"], [])
    for d in dups:
        if d["severity"] == "high":
            score += 40
            reasons.append(f"Received {d['scheme']} more than once")
        else:
            score += 15
            reasons.append(f"Applied to {d['scheme']} {d['application_count']} times")

    for r in ring_index.get(profile["citizen_id"], []):
        score += 30
        reasons.append(f"Shares a {r['identifier_type']} with {r['citizen_count'] - 1} other citizen(s)")

    if profile.get("conflicting_fields"):
        score += 5 * len(profile["conflicting_fields"])
        reasons.append("Conflicting values across departments: "
                       + ", ".join(profile["conflicting_fields"]))

    if not profile.get("aadhaar"):
        score += 10
        reasons.append("No Aadhaar on any source record")

    score = min(score, 100)
    band = "high" if score >= 60 else "medium" if score >= 30 else "low"
    return {"score": score, "band": band, "reasons": reasons or ["No risk signals found"]}


def build_indexes(golden):
    dup_index, ring_index = defaultdict(list), defaultdict(list)
    for d in duplicate_applications(golden):
        dup_index[d["citizen_id"]].append(d)
    for r in shared_identifier_rings(golden):
        for c in r["citizens"]:
            ring_index[c["citizen_id"]].append(r)
    return dup_index, ring_index
