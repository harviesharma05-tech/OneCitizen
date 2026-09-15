"""
Runs the whole platform end to end and caches the result in memory.

  CSV sources -> standardize -> resolve -> golden records
              -> fraud signals -> scheme matching -> ready to serve
"""
import csv
import glob
import json
import os
import time

from . import fraud, resolve
from .catalogue import SCHEMES
from .schemes import find_duplicate_schemes, recommend
from .standardize import standardize

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

_STATE = {}


def load_raw():
    rows = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "dept_*.csv"))):
        with open(path, newline="", encoding="utf-8") as f:
            rows.extend(list(csv.DictReader(f)))
    return rows


def run(verbose=True):
    t0 = time.time()
    raw = load_raw()
    if not raw:
        raise SystemExit("No data found. Run: python -m ubdp.generate_data")

    records = [standardize(r) for r in raw]
    clusters, review_queue, stats = resolve.resolve(records)
    golden = resolve.build_golden(records, clusters)
    accuracy = resolve.evaluate(golden)

    dup_index, ring_index = fraud.build_indexes(golden)
    for g in golden:
        g["risk"] = fraud.risk_score(g, dup_index, ring_index)
        g["recommendations"] = recommend(g, SCHEMES)

    duplicate_apps = fraud.duplicate_applications(golden)
    rings = fraud.shared_identifier_rings(golden)
    dup_schemes = find_duplicate_schemes(SCHEMES)

    impact = {
        "raw_records": stats["raw_records"],
        "golden_records": stats["golden_records"],
        "records_deduplicated": stats["raw_records"] - stats["golden_records"],
        "comparisons_avoided_pct": stats["reduction_pct"],
        "pending_review": stats["review_queue"],
        "duplicate_applications": len(duplicate_apps),
        "leakage_detected": sum(d["duplicate_amount"] for d in duplicate_apps),
        "fraud_rings": len(rings),
        "high_risk_citizens": sum(1 for g in golden if g["risk"]["band"] == "high"),
        "overlapping_schemes": len(dup_schemes),
        "new_recommendations": sum(
            1 for g in golden for r in g["recommendations"] if r["verdict"] == "eligible"),
        "total_disbursed": sum(g["total_benefit"] for g in golden),
        "runtime_seconds": round(time.time() - t0, 2),
    }

    _STATE.update({
        "records": records, "golden": golden, "review_queue": review_queue,
        "stats": stats, "accuracy": accuracy, "impact": impact,
        "duplicate_apps": duplicate_apps, "rings": rings,
        "dup_schemes": dup_schemes, "schemes": SCHEMES,
    })

    if verbose:
        report(_STATE)
    return _STATE


def state():
    return _STATE or run(verbose=False)


def report(s):
    i, a = s["impact"], s["accuracy"]
    line = "-" * 58
    print(f"\n{line}\n  UBDP PIPELINE COMPLETE  ({i['runtime_seconds']}s)\n{line}")
    print(f"  Raw department records      {i['raw_records']:>10,}")
    print(f"  Unique citizens resolved    {i['golden_records']:>10,}")
    print(f"  Duplicate records removed   {i['records_deduplicated']:>10,}")
    print(f"  Comparisons avoided         {i['comparisons_avoided_pct']:>9}%")
    print(f"  Queued for human review     {i['pending_review']:>10,}")
    print(line)
    print(f"  Duplicate applications      {i['duplicate_applications']:>10,}")
    print(f"  Leakage detected            {'₹' + format(i['leakage_detected'], ','):>10}")
    print(f"  Shared-identifier rings     {i['fraud_rings']:>10,}")
    print(f"  High-risk citizens          {i['high_risk_citizens']:>10,}")
    print(f"  Overlapping schemes found   {i['overlapping_schemes']:>10,}")
    print(f"  New eligible matches        {i['new_recommendations']:>10,}")
    print(line)
    print("  MEASURED ACCURACY (vs ground truth)")
    print(f"  False-merge rate            {a['false_merge_rate_pct']:>9}%")
    print(f"  Recall                      {a['recall_pct']:>9}%")
    print(f"{line}\n")


def export(path=None):
    s = state()
    path = path or os.path.join(DATA_DIR, "ubdp_output.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "impact": s["impact"], "accuracy": s["accuracy"],
            "golden_records": s["golden"][:25],
            "duplicate_applications": s["duplicate_apps"],
            "fraud_rings": s["rings"], "overlapping_schemes": s["dup_schemes"],
        }, f, indent=2, default=str)
    print(f"Exported results -> {path}")


if __name__ == "__main__":
    run()
    export()
