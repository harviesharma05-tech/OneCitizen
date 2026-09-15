"""
Layer 3 — Scheme intelligence.

Two jobs:
  1. Turn scheme eligibility text into machine-checkable rules, then find
     citizens who qualify (including those who never applied).
  2. Find schemes that duplicate each other.

The parser here is a transparent rule extractor over eligibility text. In
production this is the layer that upgrades to an LLM/embedding model — but
the output contract stays the same: a list of predicates the database can
check, and a reason string for every decision.
"""
import re
from itertools import combinations

from rapidfuzz import fuzz

EDU_RANK = {"none": 0, "10th": 1, "12th": 2, "graduate": 3, "postgraduate": 4}


# --------------------------------------------------------------- rule parsing
def parse_eligibility(text: str):
    """Extract structured predicates from natural-language eligibility text."""
    rules, t = [], text.lower()

    m = re.search(r"income (?:below|under|less than|upto|up to)\s*(?:rs\.?|₹)?\s*([\d,]+)", t)
    if m:
        rules.append({"field": "income", "op": "<=", "value": int(m.group(1).replace(",", "")),
                      "label": f"annual income at or below ₹{m.group(1)}"})

    m = re.search(r"age (?:above|over|at least|minimum)\s*(\d+)", t)
    if m:
        rules.append({"field": "age", "op": ">=", "value": int(m.group(1)),
                      "label": f"age {m.group(1)} or above"})

    m = re.search(r"age (?:below|under|less than|upto|up to)\s*(\d+)", t)
    if m:
        rules.append({"field": "age", "op": "<=", "value": int(m.group(1)),
                      "label": f"age {m.group(1)} or below"})

    for word, key in [("farmer", "farmer"), ("student", "student"),
                      ("labourer", "labourer"), ("unemployed", "unemployed"),
                      ("shopkeeper", "shopkeeper"), ("teacher", "teacher")]:
        if word in t:
            rules.append({"field": "occupation", "op": "==", "value": key,
                          "label": f"occupation is {key}"})
            break

    for level in ("postgraduate", "graduate", "12th", "10th"):
        if level in t:
            rules.append({"field": "education", "op": ">=", "value": level,
                          "label": f"education {level} or higher"})
            break

    m = re.search(r"land(?:holding)? (?:below|under|less than|upto|up to)\s*([\d.]+)", t)
    if m:
        rules.append({"field": "land_hectares", "op": "<=", "value": float(m.group(1)),
                      "label": f"landholding at or below {m.group(1)} hectares"})

    if "women" in t or "female" in t or "widow" in t:
        rules.append({"field": "gender", "op": "==", "value": "F",
                      "label": "applicant is female"})

    return rules


def _age(dob):
    if not dob or len(dob) < 4:
        return None
    try:
        return 2026 - int(dob[:4])
    except ValueError:
        return None


def check_rule(profile, rule):
    """Return 'pass' | 'fail' | 'unknown'. 'unknown' means data is missing —
    that is a prompt to collect it, not a rejection."""
    field = rule["field"]
    value = _age(profile.get("dob")) if field == "age" else profile.get(field)

    if value in (None, ""):
        return "unknown"

    if field == "education":
        got, need = EDU_RANK.get(str(value), -1), EDU_RANK.get(rule["value"], 99)
        return "pass" if got >= need else "fail"

    op = rule["op"]
    try:
        if op == "<=":
            return "pass" if float(value) <= float(rule["value"]) else "fail"
        if op == ">=":
            return "pass" if float(value) >= float(rule["value"]) else "fail"
        if op == "==":
            return "pass" if str(value).lower() == str(rule["value"]).lower() else "fail"
    except (TypeError, ValueError):
        return "unknown"
    return "unknown"


def match_scheme(profile, scheme):
    """Evaluate one citizen against one scheme, with a full reason trail."""
    rules = parse_eligibility(scheme["eligibility"])
    passed, failed, missing = [], [], []
    for r in rules:
        result = check_rule(profile, r)
        (passed if result == "pass" else failed if result == "fail" else missing).append(r["label"])

    already = any(s["scheme"] == scheme["name"] and s["status"] == "approved"
                  for s in profile.get("schemes", []))

    if failed:
        verdict = "not_eligible"
    elif missing:
        verdict = "needs_info"
    elif already:
        verdict = "already_enrolled"
    else:
        verdict = "eligible"

    confidence = len(passed) / len(rules) if rules else 0
    return {
        "scheme": scheme["name"],
        "department": scheme["department"],
        "verdict": verdict,
        "confidence": round(confidence, 2),
        "met": passed,
        "not_met": failed,
        "missing_info": missing,
    }


def recommend(profile, catalogue, limit=5):
    """Schemes this citizen qualifies for but has not received."""
    results = [match_scheme(profile, s) for s in catalogue]
    ranked = [r for r in results if r["verdict"] in ("eligible", "needs_info")]
    ranked.sort(key=lambda r: (r["verdict"] != "eligible", -r["confidence"], -len(r["met"])))
    return ranked[:limit]


# ------------------------------------------------------ duplicate schemes
def scheme_signature(scheme):
    rules = parse_eligibility(scheme["eligibility"])
    return {f"{r['field']}{r['op']}{r['value']}" for r in rules}


def find_duplicate_schemes(catalogue, threshold=0.62):
    """Flag scheme pairs with overlapping objective text AND eligibility rules."""
    flagged = []
    for a, b in combinations(catalogue, 2):
        text_sim = fuzz.token_set_ratio(a["objective"].lower(), b["objective"].lower()) / 100
        sig_a, sig_b = scheme_signature(a), scheme_signature(b)
        rule_overlap = (len(sig_a & sig_b) / len(sig_a | sig_b)) if (sig_a | sig_b) else 0
        combined = 0.6 * text_sim + 0.4 * rule_overlap
        if combined >= threshold:
            flagged.append({
                "scheme_a": a["name"], "dept_a": a["department"],
                "scheme_b": b["name"], "dept_b": b["department"],
                "overlap": round(combined, 2),
                "objective_similarity": round(text_sim, 2),
                "eligibility_overlap": round(rule_overlap, 2),
                "shared_criteria": sorted(sig_a & sig_b),
                "cross_department": a["department"] != b["department"],
            })
    flagged.sort(key=lambda x: -x["overlap"])
    return flagged
