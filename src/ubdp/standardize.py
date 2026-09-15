"""
Layer 1 — Ingestion & Standardization.

Every department writes data differently. Before any matching can happen,
records must be projected into one canonical schema.
"""
import re

STOPWORDS = {"h", "no", "hno", "house", "near", "road", "rd", "marg", "st",
             "street", "village", "vill", "po", "ps", "dist", "uttarakhand", "india"}

NAME_NOISE = re.compile(r"[^a-z\s]")
ADDR_NOISE = re.compile(r"[^a-z0-9\s]")
DIGITS = re.compile(r"\D")


def norm_name(value: str) -> str:
    """lowercase, strip titles/punctuation, collapse whitespace, sort tokens.

    Token sorting makes 'Ramesh Sharma' and 'Sharma Ramesh' identical, which
    is the single most common name inconsistency in Indian government data.
    """
    if not value:
        return ""
    v = NAME_NOISE.sub(" ", value.lower())
    tokens = [t for t in v.split() if t not in {"mr", "mrs", "ms", "shri", "smt", "kumari"}]
    return " ".join(sorted(tokens))


def norm_address(value: str) -> str:
    """Drop filler words and punctuation so format differences stop mattering."""
    if not value:
        return ""
    v = ADDR_NOISE.sub(" ", value.lower())
    tokens = [t for t in v.split() if t not in STOPWORDS and len(t) > 1]
    return " ".join(sorted(set(tokens)))


def norm_id(value: str) -> str:
    """Aadhaar/bank/phone: keep digits only, so spacing and dashes don't matter."""
    return DIGITS.sub("", value or "")


def norm_pan(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def norm_dob(value: str) -> str:
    """Accept YYYY-MM-DD or DD/MM/YYYY, emit YYYY-MM-DD."""
    if not value:
        return ""
    v = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return v
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", v)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return v


def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def standardize(raw: dict) -> dict:
    """Project one department row into the canonical record schema."""
    return {
        "dept_record_id": raw.get("dept_record_id", ""),
        "source_dept": raw.get("source_dept", ""),
        "name_raw": (raw.get("full_name") or "").strip(),
        "name": norm_name(raw.get("full_name")),
        "dob": norm_dob(raw.get("date_of_birth")),
        "aadhaar": norm_id(raw.get("aadhaar_no")),
        "pan": norm_pan(raw.get("pan_no")),
        "phone": norm_id(raw.get("mobile")),
        "bank_account": norm_id(raw.get("bank_account")),
        "address": norm_address(raw.get("address")),
        "address_raw": (raw.get("address") or "").strip(),
        "pincode": norm_id(raw.get("pincode")),
        "gender": (raw.get("gender") or "").strip().upper()[:1],
        "occupation": (raw.get("occupation") or "").strip().lower(),
        "income": to_int(raw.get("annual_income")),
        "education": (raw.get("education") or "").strip().lower(),
        "land_hectares": to_int(raw.get("land_hectares")),
        "scheme_applied": (raw.get("scheme_applied") or "").strip(),
        "scheme_status": (raw.get("scheme_status") or "").strip().lower(),
        "amount_disbursed": to_int(raw.get("amount_disbursed")) or 0,
        "last_updated": norm_dob(raw.get("last_updated")),
        "_truth_id": raw.get("_truth_id", ""),
    }
