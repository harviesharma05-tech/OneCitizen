"""
Layer 2 — Entity Resolution.

Pipeline:  block  ->  score pairs  ->  build graph  ->  cluster  ->  merge

This is the local, dependency-light version of the production design
(Spark blocking -> Zingg/FAISS matching -> GraphFrames clustering). The
logic is identical; only the execution engine differs.
"""
from collections import defaultdict
from itertools import combinations

import networkx as nx
from rapidfuzz import fuzz

AUTO_MERGE = 0.90      # >= this -> merged automatically
REVIEW_FLOOR = 0.60    # between floor and auto -> human review queue

# Field weights. Aadhaar/PAN dominate because they are legally unique.
WEIGHTS = {
    "aadhaar": 0.45,
    "pan": 0.25,
    "name": 0.15,
    "dob": 0.10,
    "address": 0.03,
    "phone": 0.02,
}


# ---------------------------------------------------------------- blocking
def block(records):
    """Group records into candidate buckets so we avoid an O(n^2) comparison.

    A record lands in several buckets; two records only get compared if they
    share at least one. Multiple blocking keys mean a typo in one field does
    not hide a true match.
    """
    buckets = defaultdict(list)
    for i, r in enumerate(records):
        if r["aadhaar"]:
            buckets[f"aad:{r['aadhaar']}"].append(i)
        if r["pan"]:
            buckets[f"pan:{r['pan']}"].append(i)
        if r["dob"] and r["pincode"]:
            buckets[f"dp:{r['dob']}|{r['pincode']}"].append(i)
        if r["name"] and r["pincode"]:
            initials = "".join(t[0] for t in r["name"].split()[:2])
            buckets[f"np:{initials}|{r['pincode']}"].append(i)
        if r["phone"]:
            buckets[f"ph:{r['phone']}"].append(i)
    return buckets


def candidate_pairs(records, max_bucket=400):
    """Yield unique index pairs worth scoring, with the pair count saved."""
    buckets = block(records)
    pairs = set()
    for key, idxs in buckets.items():
        if len(idxs) < 2 or len(idxs) > max_bucket:
            continue  # oversized buckets are useless blocks, skip them
        for a, b in combinations(sorted(set(idxs)), 2):
            pairs.add((a, b))
    naive = len(records) * (len(records) - 1) // 2
    return sorted(pairs), naive


# ----------------------------------------------------------------- scoring
def score_pair(a, b):
    """Return (score, explanation list). Explanations drive the audit trail."""
    # Deterministic short-circuit: a shared government ID is decisive.
    if a["aadhaar"] and a["aadhaar"] == b["aadhaar"]:
        return 1.0, ["Aadhaar number matches exactly"]
    if a["pan"] and a["pan"] == b["pan"]:
        return 0.97, ["PAN number matches exactly"]

    # ---- Tier 2: composite evidence.
    # No single ID, but several independent quasi-identifiers agreeing is
    # itself strong proof. A shared bank account plus a matching DOB and
    # name is not a coincidence.
    name_sim = fuzz.token_sort_ratio(a["name"], b["name"]) / 100 if (a["name"] and b["name"]) else None
    dob_match = bool(a["dob"] and a["dob"] == b["dob"])
    phone_match = bool(a["phone"] and a["phone"] == b["phone"])
    bank_match = bool(a["bank_account"] and a["bank_account"] == b["bank_account"])
    addr_sim = fuzz.token_set_ratio(a["address"], b["address"]) / 100 if (a["address"] and b["address"]) else None

    strong = sum([dob_match, phone_match, bank_match,
                  bool(name_sim is not None and name_sim >= 0.90)])

    if bank_match and dob_match and name_sim is not None and name_sim >= 0.80:
        why = ["Bank account matches", "Date of birth matches",
               f"Name similarity {name_sim:.0%}"]
        return 0.94, why
    if phone_match and dob_match and name_sim is not None and name_sim >= 0.80:
        why = ["Mobile number matches", "Date of birth matches",
               f"Name similarity {name_sim:.0%}"]
        return 0.93, why
    if strong >= 3:
        why = ["Three or more independent identifiers agree"]
        return 0.92, why

    # ---- Tier 3: weighted probabilistic score.
    earned, available, why = 0.0, 0.0, []

    if name_sim is not None:
        earned += WEIGHTS["name"] * name_sim
        available += WEIGHTS["name"]
        why.append(f"Name similarity {name_sim:.0%}")

    if a["dob"] and b["dob"]:
        earned += WEIGHTS["dob"] * (1.0 if dob_match else 0.0)
        available += WEIGHTS["dob"]
        why.append("Date of birth matches" if dob_match else "Date of birth differs")

    if addr_sim is not None:
        earned += WEIGHTS["address"] * addr_sim
        available += WEIGHTS["address"]
        if addr_sim > 0.8:
            why.append(f"Address similarity {addr_sim:.0%}")

    if a["phone"] and b["phone"]:
        earned += WEIGHTS["phone"] * (1.0 if phone_match else 0.0)
        available += WEIGHTS["phone"]
        if phone_match:
            why.append("Mobile number matches")

    if available == 0:
        return 0.0, ["No comparable fields"]

    score = earned / available

    # Weak evidence never reaches the auto-merge lane. Anything decided on
    # fuzzy signals alone goes to a human instead.
    score = min(score, 0.88)
    why.append("Decided on fuzzy evidence only — held below auto-merge")

    if a["pincode"] and b["pincode"] and a["pincode"] != b["pincode"]:
        score *= 0.85
        why.append("Different pincode — score reduced")

    return round(score, 4), why


# ---------------------------------------------------------- graph clustering
def resolve(records):
    """Run the full pipeline. Returns clusters, review queue, and stats."""
    pairs, naive = candidate_pairs(records)

    graph = nx.Graph()
    graph.add_nodes_from(range(len(records)))
    review_queue, auto_links = [], []

    for i, j in pairs:
        score, why = score_pair(records[i], records[j])
        if score >= AUTO_MERGE:
            graph.add_edge(i, j, score=score, why=why)
            auto_links.append((i, j, score, why))
        elif score >= REVIEW_FLOOR:
            review_queue.append({
                "left": records[i], "right": records[j],
                "score": score, "reasons": why,
            })

    # Connected components = one real-world person each.
    clusters = [sorted(c) for c in nx.connected_components(graph)]
    clusters.sort(key=lambda c: (-len(c), c[0]))

    stats = {
        "raw_records": len(records),
        "naive_comparisons": naive,
        "compared_pairs": len(pairs),
        "reduction_pct": round(100 * (1 - len(pairs) / naive), 2) if naive else 0,
        "auto_merged_links": len(auto_links),
        "review_queue": len(review_queue),
        "golden_records": len(clusters),
    }
    return clusters, review_queue, stats


# ----------------------------------------------------------- golden records
def _freshest(records, field):
    """Conflicting values resolve to the most recently updated source."""
    candidates = [r for r in records if r.get(field) not in (None, "", 0)]
    if not candidates:
        return None, None
    best = max(candidates, key=lambda r: r["last_updated"] or "")
    return best[field], best["source_dept"]


def build_golden(records, clusters):
    """Merge each cluster into one consolidated citizen profile."""
    golden = []
    for cid, idxs in enumerate(clusters, start=1):
        members = [records[i] for i in idxs]
        profile = {"citizen_id": f"UBDP-{cid:05d}", "source_record_count": len(members)}

        # Union unique fields, freshest-wins on conflicts.
        provenance, conflicts = {}, []
        for field in ("name_raw", "dob", "aadhaar", "pan", "phone", "bank_account",
                      "address_raw", "pincode", "gender", "occupation", "income",
                      "education", "land_hectares"):
            value, src = _freshest(members, field)
            profile[field] = value
            if src:
                provenance[field] = src
            distinct = {m[field] for m in members if m.get(field) not in (None, "", 0)}
            if len(distinct) > 1:
                conflicts.append(field)

        profile["departments"] = sorted({m["source_dept"] for m in members})
        profile["provenance"] = provenance
        profile["conflicting_fields"] = conflicts

        # Benefit ledger — the transparency/proof trail.
        profile["schemes"] = [{
            "scheme": m["scheme_applied"],
            "department": m["source_dept"],
            "status": m["scheme_status"],
            "amount": m["amount_disbursed"],
            "date": m["last_updated"],
            "source_record_id": m["dept_record_id"],
        } for m in members if m["scheme_applied"]]

        profile["total_benefit"] = sum(
            s["amount"] for s in profile["schemes"] if s["status"] == "approved")
        profile["_truth_ids"] = sorted({m["_truth_id"] for m in members if m["_truth_id"]})
        golden.append(profile)
    return golden


def evaluate(golden):
    """Score the engine against ground truth. Never used in production —
    exists so the false-merge rate is a measured number, not a claim."""
    impure = sum(1 for g in golden if len(g["_truth_ids"]) > 1)
    truth_to_clusters = defaultdict(int)
    for g in golden:
        for t in g["_truth_ids"]:
            truth_to_clusters[t] += 1
    split = sum(1 for t, n in truth_to_clusters.items() if n > 1)
    return {
        "clusters": len(golden),
        "true_people_seen": len(truth_to_clusters),
        "false_merges": impure,
        "false_merge_rate_pct": round(100 * impure / max(len(golden), 1), 2),
        "under_merged_people": split,
        "recall_pct": round(100 * (1 - split / max(len(truth_to_clusters), 1)), 2),
    }
