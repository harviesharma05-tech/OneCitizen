"""
Layer 4 — Role-based access control with field-level masking.

Two separate questions, deliberately kept separate:
  1. Which citizens may this user see?   (row-level scope)
  2. Which fields may they see in full?  (field-level masking)

A dashboard that hides a column but ships the value in the API response is
not access control. Masking happens server-side, before serialisation.
"""

SENSITIVE = {"aadhaar", "pan", "bank_account", "phone"}

ROLES = {
    "commissioner": {
        "label": "State Commissioner",
        "departments": "ALL",
        "can_see_sensitive": True,
        "can_review_merges": True,
        "can_see_fraud": True,
        "can_see_impact": True,
    },
    "dept_officer": {
        "label": "Department Officer",
        "departments": "OWN",
        "can_see_sensitive": True,
        "can_review_merges": True,
        "can_see_fraud": True,
        "can_see_impact": False,
    },
    "field_operator": {
        "label": "Field Data Operator",
        "departments": "OWN",
        "can_see_sensitive": False,
        "can_review_merges": False,
        "can_see_fraud": False,
        "can_see_impact": False,
    },
    "auditor": {
        "label": "Independent Auditor",
        "departments": "ALL",
        "can_see_sensitive": False,
        "can_review_merges": False,
        "can_see_fraud": True,
        "can_see_impact": True,
    },
}

USERS = {
    "commissioner":  {"password": "demo", "role": "commissioner",  "department": None,
                      "name": "R. Nautiyal"},
    "agri_officer":  {"password": "demo", "role": "dept_officer",  "department": "Agriculture",
                      "name": "S. Rawat"},
    "housing_officer": {"password": "demo", "role": "dept_officer", "department": "Housing",
                        "name": "M. Bisht"},
    "welfare_officer": {"password": "demo", "role": "dept_officer", "department": "SocialWelfare",
                        "name": "A. Negi"},
    "operator":      {"password": "demo", "role": "field_operator", "department": "Education",
                      "name": "P. Joshi"},
    "auditor":       {"password": "demo", "role": "auditor",       "department": None,
                      "name": "CAG Cell"},
}


def authenticate(username, password):
    user = USERS.get(username)
    if user and user["password"] == password:
        return {**user, "username": username, "perms": ROLES[user["role"]]}
    return None


def mask(value, keep=4):
    """Show only the trailing characters. Never send the full value."""
    if not value:
        return ""
    v = str(value)
    return "•" * max(len(v) - keep, 0) + v[-keep:] if len(v) > keep else "•" * len(v)


def visible_citizens(golden, user):
    """Row-level scope: officers only see citizens touching their department."""
    perms = user["perms"]
    if perms["departments"] == "ALL":
        return golden
    dept = user["department"]
    return [g for g in golden if dept in g["departments"]]


def project(profile, user):
    """Field-level masking applied before the record leaves the server."""
    perms = user["perms"]
    out = dict(profile)
    out.pop("_truth_ids", None)          # ground truth never leaves the lab

    if not perms["can_see_sensitive"]:
        for field in SENSITIVE:
            out[field] = mask(out.get(field))

    if not perms["can_see_fraud"]:
        out.pop("risk", None)

    # Officers see only their own department's entries in the benefit ledger.
    if perms["departments"] != "ALL":
        out["schemes"] = [s for s in out.get("schemes", [])
                          if s["department"] == user["department"]]
    return out


def audit_line(user, action, target):
    """Every privileged read is logged. Transparency cuts both ways."""
    return {"user": user["username"], "role": user["role"],
            "action": action, "target": target}
