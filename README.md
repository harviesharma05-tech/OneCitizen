# UBDP — Unified Beneficiary Data Platform

Welfare beneficiary data sits in separate departmental systems. The same person
appears many times over under slightly different spellings, half the records are
missing an Aadhaar number, nobody can see what a citizen has already received, and
eligible people never get told a scheme exists.

This is a working prototype that resolves those records into one verified profile
per citizen, then uses that profile to recommend schemes, detect duplicate payouts,
flag overlapping schemes, and serve role-scoped dashboards.

Everything below runs locally in under a second on synthetic data.

---

## What it actually does

| Requirement | Where it's implemented |
|---|---|
| Combine a beneficiary's data across departments | `resolve.py` — blocking, matching, graph clustering, golden record merge |
| Identify duplicate identities | `resolve.py` + `fraud.py` — duplicate applications to the same scheme |
| Recommend a scheme to the right people | `schemes.py` — eligibility rules checked against each profile |
| Identify schemes that duplicate each other | `schemes.py` — objective similarity plus eligibility-rule overlap |
| Role-based, department-wise dashboards | `rbac.py` + `app.py` — row scoping and server-side field masking |
| See every scheme a person has taken | Benefit ledger on each golden record |
| Find people who qualify but never applied | Recommendations run against all citizens, not just applicants |
| Transparency | Proof trail per benefit, plus an access log of every privileged read |

---

## Measured results

Run on 348 synthetic records across 5 departments, scored against ground truth:

```
Raw department records             348
Unique citizens resolved           122
Duplicate records removed          226
Comparisons avoided              99.1%      (blocking vs. all-pairs)
Queued for human review              7

False-merge rate                  0.00%
Recall                           98.33%
```

The accuracy numbers are computed by `resolve.evaluate()` against labels the
matching engine never sees. They are measured, not claimed.

---

## Running it

```bash
pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000 and sign in. Password for every demo account is `demo`.

| Username | Role | What they can see |
|---|---|---|
| `commissioner` | State Commissioner | Everything, all departments |
| `agri_officer` | Department Officer | Agriculture citizens only, full detail |
| `housing_officer` | Department Officer | Housing citizens only |
| `operator` | Field Data Operator | Education only, Aadhaar/PAN/bank masked, no fraud view |
| `auditor` | Independent Auditor | All departments, but all identifiers masked |

Sign in as `commissioner`, then as `operator`, and compare. The masking happens
server-side in `rbac.project()` — the browser never receives the hidden values.

To run the pipeline without the web layer:

```bash
python -m ubdp.generate_data    # regenerate synthetic departments
python -m ubdp.pipeline         # run end to end, print the scorecard
```

---

## How the matching works

**1. Standardize.** Lowercase, strip punctuation, drop address filler words, sort
name tokens (so `Ramesh Sharma` and `Sharma Ramesh` become identical), normalise
Aadhaar/phone/bank to digits, unify date formats.

**2. Block.** Comparing every record against every other is O(n²). Instead each
record is indexed under several keys — Aadhaar, PAN, DOB+pincode, name-initials+
pincode, phone — and only records sharing a key get compared. This cuts 99% of
comparisons while keeping recall high, because a typo in one field can't hide a
match that another key catches.

**3. Score, in three tiers.**

- *Deterministic.* Same Aadhaar → 1.0. Same PAN → 0.97. A legally unique ID is decisive.
- *Composite.* No shared ID, but bank account + DOB + name agreeing is not a
  coincidence → 0.92–0.94. This tier is what lifts recall from 55% to 98%, because
  roughly a fifth of real records have no Aadhaar at all.
- *Probabilistic.* Weighted fuzzy similarity, and **capped at 0.88** so it can never
  reach the auto-merge line. Anything decided on fuzzy evidence alone goes to a human.

**4. Cluster.** Matches become edges in a graph; each connected component is one
real person. This is transitive — if A matches B and B matches C, all three merge,
even when A and C share no field directly.

**5. Merge.** Union all fields, freshest source wins on conflicts, provenance
recorded per field, conflicts listed rather than silently resolved.

### Why the threshold is defensible

`AUTO_MERGE = 0.90` only ever admits records with either a shared government ID or
three independent agreeing identifiers. Fuzzy-only evidence is structurally capped
below it. That is why the measured false-merge rate is 0% rather than a hope — the
cap is the mechanism, not the number.

---

## Scheme matching

`parse_eligibility()` turns eligibility text into checkable predicates:

```
"farmer with landholding below 2.0 hectares and annual income below 200000"
  -> occupation == farmer
  -> land_hectares <= 2.0
  -> income <= 200000
```

Each predicate returns `pass`, `fail`, or **`unknown`**. `unknown` matters: a
citizen missing an income figure is not rejected, they are surfaced as *blocked only
by missing information*, with a prompt for exactly the field needed. Every
recommendation carries the conditions it met, so no decision is a black box.

Duplicate schemes are flagged on a blend of objective-text similarity and
eligibility-rule overlap — two schemes can be worded differently and still target
an identical population.

---

## Fraud signals

- **Duplicate applications** — same resolved citizen, same scheme, more than once.
  Only detectable *after* entity resolution, which is the point.
- **Shared identifiers** — distinct citizens sharing a bank account or mobile
  number. The classic ghost-beneficiary pattern.
- **Risk score** (0–100) per citizen, always with the reasons that produced it.

---

## Project layout

```
src/ubdp/
  generate_data.py   synthetic department CSVs, with realistic mess injected
  standardize.py     layer 1 — cleaning and canonical schema
  resolve.py         layer 2 — blocking, scoring, clustering, golden records
  schemes.py         layer 3 — eligibility parsing, recommendations, overlap
  catalogue.py       15 schemes across 5 departments
  fraud.py           duplicate payouts, shared-identifier rings, risk scoring
  rbac.py            layer 4 — roles, row scoping, field masking
  pipeline.py        orchestrator + scorecard
  app.py             Flask server and JSON API
web/                 dashboard templates, stylesheet, client logic
data/                generated CSVs and exported JSON
```

---

## Prototype vs. production

The prototype runs single-machine so it can be cloned and demoed in one command.
The logic is written to survive the swap; only the execution engine changes.

| Stage | Prototype | Production |
|---|---|---|
| Ingestion | CSV reader | Spark / Databricks with CDC from department DBs |
| Storage | in-memory | Delta Lake |
| Blocking | dict index | Spark blocking, FAISS embeddings for fuzzy blocks |
| Matching | rapidfuzz + rules | Zingg, same rule tiers |
| Clustering | NetworkX | GraphFrames connected components |
| Serving | Flask | Snowflake / BigQuery behind the same API |

---

## Known limits

Worth stating plainly rather than being asked:

- **Synthetic data.** Real government records are messier — transliteration variants
  across scripts, shared family bank accounts that are legitimate, and addresses far
  less structured than these.
- **The eligibility parser is a rule extractor, not a language model.** It handles
  the phrasings in `catalogue.py`. Real scheme documents are inconsistent and
  ambiguous, and this is the component most likely to break first. The output
  contract (predicates plus reasons) is designed so an LLM can replace the parser
  without touching anything downstream.
- **Consent is not implemented.** Linking Aadhaar-bearing records across departments
  requires a lawful basis under the DPDP Act 2023 and the Aadhaar Act. A real
  deployment needs consent capture at enrolment and purpose limitation per
  department. Field-level masking here is a technical control, not a legal one.
- **Review decisions don't persist.** The merge-review UI accepts a decision but
  does not write it back or retrain. The feedback loop is designed, not built.
- **No production hardening.** Demo secret key, no HTTPS, passwords in plaintext in
  `rbac.py`. Deliberate, so the demo runs anywhere without setup.
