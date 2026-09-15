"""
Generates synthetic department databases for the UBDP demo.

Simulates the real-world mess: same person appears across departments with
inconsistent spellings, missing IDs, stale addresses, and outright duplicate
applications to the same scheme.
"""
import csv
import os
import random

random.seed(42)

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data")

FIRST = ["Ramesh", "Sunita", "Arjun", "Priya", "Mohan", "Kavita", "Deepak",
         "Anita", "Vikram", "Meena", "Suresh", "Pooja", "Rajesh", "Neha",
         "Amit", "Lakshmi", "Harish", "Geeta", "Sanjay", "Rekha"]
LAST = ["Sharma", "Verma", "Patel", "Singh", "Kumar", "Yadav", "Joshi",
        "Rawat", "Negi", "Bisht", "Gupta", "Chauhan"]
CITIES = [("Haridwar", "249401"), ("Dehradun", "248001"), ("Roorkee", "247667"),
          ("Rishikesh", "249201"), ("Haldwani", "263139")]
OCCUPATIONS = ["farmer", "student", "labourer", "shopkeeper", "teacher", "unemployed"]

# Typo / inconsistency injectors that mimic real data entry
def messy_name(name):
    r = random.random()
    if r < 0.15:
        return name.upper()
    if r < 0.25:
        return name.replace("a", "aa", 1)
    if r < 0.32:
        return name.replace("i", "ee", 1)
    if r < 0.40:
        return "  " + name + " "
    if r < 0.46 and len(name.split()) == 2:
        f, l = name.split()
        return f"{l} {f}"          # name order swapped
    return name


def messy_address(city, pin):
    house = random.randint(1, 250)
    street = random.choice(["Main Road", "Gandhi Marg", "Station Rd",
                            "Nehru Nagar", "Shivalik Vihar"])
    fmt = random.random()
    if fmt < 0.3:
        return f"H.No {house}, {street}, {city} - {pin}"
    if fmt < 0.6:
        return f"{house} {street} {city} {pin}"
    return f"{house}/{street.lower()}, {city.lower()}, uttarakhand, {pin}"


def make_people(n=120):
    people = []
    for i in range(n):
        city, pin = random.choice(CITIES)
        fn, ln = random.choice(FIRST), random.choice(LAST)
        people.append({
            "truth_id": f"P{i:04d}",
            "name": f"{fn} {ln}",
            "dob": f"{random.randint(1955, 2006)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "aadhaar": f"{random.randint(2,9)}{random.randint(100,999)}{random.randint(1000,9999)}{random.randint(1000,9999)}",
            "pan": f"{''.join(random.choices('ABCDEFGHJK', k=5))}{random.randint(1000,9999)}{random.choice('ABCDEFG')}",
            "phone": f"9{random.randint(100000000, 999999999)}",
            "bank_acct": f"{random.randint(10**10, 10**11 - 1)}",
            "city": city, "pin": pin,
            "occupation": random.choice(OCCUPATIONS),
            "income": random.choice([45000, 80000, 120000, 180000, 250000, 400000, 650000]),
            "education": random.choice(["none", "10th", "12th", "graduate", "postgraduate"]),
            "land_hectares": round(random.uniform(0, 4), 2),
            "gender": random.choice(["F", "M"]),
        })
    return people


def _recent_date():
    """Any date between 2023 and today (Sept 2026) — never the future."""
    year = random.randint(2023, 2026)
    month = random.randint(1, 9) if year == 2026 else random.randint(1, 12)
    return f"{year}-{month:02d}-{random.randint(1, 28):02d}"


def emit_record(p, dept, scheme, drop_aadhaar=False, drop_pan=False,
                shared_bank=None, shared_phone=None):
    """Project a person into one department's schema, with realistic gaps."""
    return {
        "dept_record_id": f"{dept[:3].upper()}-{random.randint(100000, 999999)}",
        "source_dept": dept,
        "full_name": messy_name(p["name"]),
        "date_of_birth": p["dob"] if random.random() > 0.08 else "",
        "aadhaar_no": "" if drop_aadhaar else (p["aadhaar"] if random.random() > 0.12 else ""),
        "pan_no": "" if drop_pan else (p["pan"] if random.random() > 0.45 else ""),
        "mobile": shared_phone or p["phone"],
        "bank_account": shared_bank or p["bank_acct"],
        "address": messy_address(p["city"], p["pin"]),
        "pincode": p["pin"],
        "gender": p["gender"],
        "occupation": p["occupation"] if random.random() > 0.2 else "",
        "annual_income": p["income"] if random.random() > 0.25 else "",
        "education": p["education"] if random.random() > 0.3 else "",
        "land_hectares": p["land_hectares"] if dept == "Agriculture" else "",
        "scheme_applied": scheme,
        "scheme_status": random.choice(["approved", "approved", "approved", "pending", "rejected"]),
        "amount_disbursed": random.choice([0, 6000, 12000, 25000, 50000, 120000]),
        "last_updated": _recent_date(),
        "_truth_id": p["truth_id"],   # ground truth, for scoring only — never used by the engine
    }


DEPT_SCHEMES = {
    "Agriculture": ["PM-Kisan Samman Nidhi", "Krishi Sinchai Yojana", "Kisan Credit Support"],
    "Housing":     ["PM Awas Yojana (Gramin)", "State Housing Subsidy", "Rural Shelter Grant"],
    "SocialWelfare": ["Old Age Pension", "Widow Pension Scheme", "Disability Support Allowance"],
    "Education":   ["Post-Matric Scholarship", "Merit Scholarship for PG", "Skill Training Stipend"],
    "RuralDev":    ["MGNREGA Wage Support", "Rural Livelihood Mission", "Village Infra Grant"],
}


def build():
    os.makedirs(OUT, exist_ok=True)
    people = make_people(120)
    dept_rows = {d: [] for d in DEPT_SCHEMES}

    # Each person appears in 1-4 departments
    for p in people:
        depts = random.sample(list(DEPT_SCHEMES), k=random.randint(1, 4))
        for d in depts:
            scheme = random.choice(DEPT_SCHEMES[d])
            dept_rows[d].append(emit_record(
                p, d, scheme,
                drop_aadhaar=(random.random() < 0.18),
                drop_pan=(random.random() < 0.5),
            ))

    # --- Inject duplicate applications to the SAME scheme (requirement ii) ---
    for p in random.sample(people, 12):
        d = random.choice(list(DEPT_SCHEMES))
        scheme = random.choice(DEPT_SCHEMES[d])
        dept_rows[d].append(emit_record(p, d, scheme, drop_aadhaar=True))
        dept_rows[d].append(emit_record(p, d, scheme, drop_pan=True))

    # --- Inject fraud rings: distinct identities sharing a bank account/phone ---
    fraud_bank = "88" + str(random.randint(10**8, 10**9 - 1))
    fraud_phone = "9" + str(random.randint(10**8, 10**9 - 1))
    for p in random.sample(people, 5):
        d = random.choice(list(DEPT_SCHEMES))
        dept_rows[d].append(emit_record(
            p, d, random.choice(DEPT_SCHEMES[d]),
            shared_bank=fraud_bank, shared_phone=fraud_phone))

    cols = list(dept_rows["Agriculture"][0].keys())
    for dept, rows in dept_rows.items():
        random.shuffle(rows)
        path = os.path.join(OUT, f"dept_{dept.lower()}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"  wrote {len(rows):4d} records -> {os.path.basename(path)}")

    return sum(len(r) for r in dept_rows.values())


if __name__ == "__main__":
    print("Generating synthetic department databases...")
    total = build()
    print(f"Done. {total} raw records across {len(DEPT_SCHEMES)} departments.")
