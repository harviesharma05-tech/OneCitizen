"""
UBDP Assistant — a small, transparent chatbot.

Deliberately rule-based rather than calling an external LLM: it needs to run
offline, deterministically, and inside a hackathon demo with no API keys.
Every answer is traceable to a fixed template or the scheme catalogue —
there is nothing generative here to hallucinate a wrong eligibility rule.

Language handling: if the message contains Devanagari characters, reply in
Hindi; otherwise reply in English. Hinglish (Hindi typed in Latin script) is
matched by keyword, but answered in English, since there is no reliable way
to detect Hinglish-vs-English from keywords alone without a language model.
"""
import re

from rapidfuzz import fuzz, process

from .catalogue import SCHEMES
from .schemes import parse_eligibility

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
FILLER = re.compile(
    r"\b(kya|hai|h|about|tell|me|the|is|of|please|batao|बताओ|के|बारे|में|क्या|है)\b",
    re.I)

OCCUPATION_WORDS = {
    "farmer": ["farmer", "kisan", "krishak", "किसान", "कृषक"],
    "student": ["student", "vidyarthi", "chatra", "विद्यार्थी", "छात्र", "student"],
    "labourer": ["labour", "mazdoor", "worker", "मजदूर"],
    "unemployed": ["unemployed", "berozgar", "बेरोजगार", "jobless"],
    "shopkeeper": ["shopkeeper", "dukandar", "दुकानदार", "business"],
    "teacher": ["teacher", "shikshak", "शिक्षक"],
}
WOMEN_WORDS = ["women", "woman", "female", "widow", "mahila", "vidhwa", "महिला", "विधवा"]
ELDERLY_WORDS = ["elderly", "senior citizen", "old age", "budhapa", "buzurg", "बुजुर्ग", "वृद्ध"]

DEPT_WORDS = {
    "Agriculture": ["agriculture", "krishi", "farming", "कृषि"],
    "Housing": ["housing", "awas", "ghar", "आवास", "घर"],
    "SocialWelfare": ["welfare", "pension", "samajik", "सामाजिक", "पेंशन"],
    "Education": ["education", "scholarship", "shiksha", "शिक्षा", "छात्रवृत्ति"],
    "RuralDev": ["rural", "gramin", "gaon", "ग्रामीण", "गांव", "mgnrega"],
}

ROADMAP = [
    {
        "phase_en": "Phase 1 — Prototype (now)",
        "phase_hi": "चरण 1 — प्रोटोटाइप (अभी)",
        "items_en": ["Entity resolution engine on synthetic data",
                     "Rule-based scheme matching and duplicate-scheme detection",
                     "Role-based dashboard with field-level masking",
                     "Fraud signal detection (duplicate payouts, shared identifiers)"],
        "items_hi": ["सिंथेटिक डेटा पर एंटिटी रेज़ोल्यूशन इंजन",
                     "रूल-आधारित स्कीम मैचिंग और डुप्लिकेट-स्कीम पहचान",
                     "फील्ड-लेवल मास्किंग के साथ रोल-आधारित डैशबोर्ड",
                     "फ्रॉड सिग्नल डिटेक्शन (डुप्लिकेट भुगतान, साझा पहचान)"],
    },
    {
        "phase_en": "Phase 2 — Pilot (3–6 months)",
        "phase_hi": "चरण 2 — पायलट (3–6 महीने)",
        "items_en": ["Integrate 2–3 real district databases",
                     "Human review workflow goes live for low-confidence matches",
                     "Consent capture at login, DPDP Act–compliant purpose limitation",
                     "Multilingual NLP for scheme eligibility parsing (Hindi + regional)"],
        "items_hi": ["2–3 वास्तविक जिला डेटाबेस को जोड़ना",
                     "कम-विश्वास वाले मिलानों के लिए मानव समीक्षा कार्यप्रवाह चालू करना",
                     "लॉगिन पर सहमति और DPDP अधिनियम अनुपालन",
                     "स्कीम पात्रता विश्लेषण के लिए बहुभाषी NLP (हिंदी + क्षेत्रीय भाषाएं)"],
    },
    {
        "phase_en": "Phase 3 — Scale (6–12 months)",
        "phase_hi": "चरण 3 — विस्तार (6–12 महीने)",
        "items_en": ["State-wide rollout across all departments",
                     "CSC / SMS-based access for low-connectivity areas",
                     "Feedback loop — review decisions retrain the matching model",
                     "Grievance and appeal mechanism for wrongful merges or rejections"],
        "items_hi": ["सभी विभागों में राज्यव्यापी रोलआउट",
                     "कम कनेक्टिविटी क्षेत्रों के लिए CSC / SMS आधारित पहुंच",
                     "फीडबैक लूप — समीक्षा निर्णयों से मॉडल को दोबारा प्रशिक्षित करना",
                     "गलत मर्ज या अस्वीकृति के लिए शिकायत तंत्र"],
    },
    {
        "phase_en": "Phase 4 — Maturity (12+ months)",
        "phase_hi": "चरण 4 — परिपक्वता (12+ महीने)",
        "items_en": ["Cross-state interoperability for migrant beneficiaries",
                     "Policymaker impact dashboard (fraud caught, funds saved, new reach)",
                     "Tamper-evident proof ledger for every disbursal",
                     "Independent audit and compliance certification"],
        "items_hi": ["प्रवासी लाभार्थियों के लिए अंतर-राज्य इंटरऑपरेबिलिटी",
                     "नीति-निर्माताओं के लिए प्रभाव डैशबोर्ड (पकड़ा गया फ्रॉड, बचाई गई राशि)",
                     "हर भुगतान के लिए छेड़छाड़-रोधी प्रूफ लेजर",
                     "स्वतंत्र ऑडिट और अनुपालन प्रमाणन"],
    },
]


def detect_lang(text: str) -> str:
    return "hi" if DEVANAGARI.search(text) else "en"


def _match_occupation(t):
    for key, words in OCCUPATION_WORDS.items():
        if any(w in t for w in words):
            return key
    return None


def _match_department(t):
    for dept, words in DEPT_WORDS.items():
        if any(w in t for w in words):
            return dept
    return None


def _clean_for_match(text: str) -> str:
    """Strip question filler ('kya hai', 'tell me about', ...) and
    punctuation so scheme-name matching isn't thrown off by conversational
    wrapping around the actual scheme name."""
    stripped = re.sub(r"[()?]", " ", text)
    stripped = FILLER.sub(" ", stripped)
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _scheme_lookup(t):
    cleaned = _clean_for_match(t)
    if not cleaned:
        return None
    options = {s["name"]: _clean_for_match(s["name"]) for s in SCHEMES}
    hit = process.extractOne(cleaned, list(options.values()),
                             scorer=fuzz.token_set_ratio, score_cutoff=78)
    if hit:
        matched_name = next(k for k, v in options.items() if v == hit[0])
        return next(s for s in SCHEMES if s["name"] == matched_name)
    return None


def _format_scheme(s, lang):
    if lang == "hi":
        return (f"**{s['name']}** ({s['department']})\n"
                f"उद्देश्य: {s['objective']}\n"
                f"पात्रता: {s['eligibility']}\n"
                f"लाभ: {s['benefit']}")
    return (f"**{s['name']}** ({s['department']})\n"
            f"Objective: {s['objective']}\n"
            f"Eligibility: {s['eligibility']}\n"
            f"Benefit: {s['benefit']}")


def _roadmap_text(lang):
    lines = []
    for phase in ROADMAP:
        title = phase["phase_hi"] if lang == "hi" else phase["phase_en"]
        items = phase["items_hi"] if lang == "hi" else phase["items_en"]
        lines.append(f"**{title}**")
        lines.extend(f"  · {it}" for it in items)
    return "\n".join(lines)


def _schemes_for_occupation(occupation):
    out = []
    for s in SCHEMES:
        rules = parse_eligibility(s["eligibility"])
        if any(r["field"] == "occupation" and r["value"] == occupation for r in rules):
            out.append(s)
    return out


GREETING_WORDS = ["hi", "hello", "hey", "namaste", "नमस्ते", "namaskar"]
ROADMAP_WORDS = ["roadmap", "future", "plan", "next steps",
                 "रोडमैप", "आगे", "भविष्य", "आगे की योजना"]
HOW_WORDS = ["how does", "how it works", "kaise kaam", "kaam kaise", "कैसे काम"]
DUP_WORDS = ["duplicate", "fraud", "dobara", "dubara", "फर्जी", "धोखा", "डुप्लिकेट"]
LIST_WORDS = ["list", "all schemes", "sari scheme", "schemes hai", "सभी योजना", "सारी योजना"]


def respond(message: str) -> dict:
    lang = detect_lang(message)
    t = message.lower().strip()

    if not t:
        return _reply("Ask me about a scheme, eligibility, or the project roadmap.",
                      "किसी योजना, पात्रता, या प्रोजेक्ट रोडमैप के बारे में पूछें।", lang)

    if any(w in t for w in GREETING_WORDS) and len(t) < 20:
        return _reply(
            "Hi! I can tell you about any welfare scheme, check who qualifies, "
            "or walk you through the project roadmap. What would you like to know?",
            "नमस्ते! मैं आपको किसी भी योजना के बारे में बता सकता हूं, पात्रता जांच सकता हूं, "
            "या प्रोजेक्ट रोडमैप बता सकता हूं। आप क्या जानना चाहेंगे?", lang)

    if any(w in t for w in ROADMAP_WORDS):
        return _reply(_roadmap_text("en"), _roadmap_text("hi"), lang, raw=True)

    if any(w in t for w in LIST_WORDS):
        names = "\n".join(f"  · {s['name']} — {s['department']}" for s in SCHEMES)
        return _reply(f"Here are all {len(SCHEMES)} schemes in the catalogue:\n{names}",
                      f"कैटलॉग में सभी {len(SCHEMES)} योजनाएं:\n{names}", lang, raw=True)

    if any(w in t for w in HOW_WORDS):
        return _reply(
            "Records from every department are cleaned into one format, matched using "
            "Aadhaar/PAN where available (or DOB + bank account + name together when "
            "not), and merged into one profile per citizen. That profile is then "
            "checked against every scheme's eligibility rules automatically.",
            "हर विभाग के रिकॉर्ड एक फॉर्मेट में साफ किए जाते हैं, आधार/पैन से मिलान किया जाता है "
            "(या न होने पर जन्मतिथि + बैंक खाता + नाम एक साथ), और हर नागरिक की एक प्रोफ़ाइल "
            "में मिला दिया जाता है। फिर उस प्रोफ़ाइल को हर योजना की पात्रता शर्तों से स्वतः जांचा जाता है।",
            lang)

    if any(w in t for w in DUP_WORDS):
        return _reply(
            "The system flags a citizen who received the same scheme more than once, "
            "and flags different identities that share a bank account or mobile "
            "number — both are checked automatically once records are merged.",
            "सिस्टम उन नागरिकों को चिन्हित करता है जिन्हें एक ही योजना का लाभ एक से अधिक बार मिला, "
            "और उन अलग-अलग पहचानों को भी जो एक ही बैंक खाता या मोबाइल नंबर साझा करती हैं — "
            "रिकॉर्ड मिलने के बाद दोनों की जांच अपने आप होती है।", lang)

    # A specific scheme name is more precise than a department keyword, so
    # it's checked first — "PM Awas Yojana" should return that one scheme,
    # not every Housing scheme.
    scheme = _scheme_lookup(t)
    if scheme:
        block = _format_scheme(scheme, lang)
        return _reply(block, block, lang, raw=True)

    dept = _match_department(t)
    if dept:
        matches = [s for s in SCHEMES if s["department"] == dept]
        block = "\n\n".join(_format_scheme(s, lang) for s in matches)
        return _reply(block, block, lang, raw=True)

    occupation = _match_occupation(t)
    if occupation:
        matches = _schemes_for_occupation(occupation)
        if matches:
            block = "\n\n".join(_format_scheme(s, lang) for s in matches)
            return _reply(f"Schemes that apply to a {occupation}:\n\n{block}",
                          f"इनके लिए योजनाएं ({occupation}):\n\n{block}", lang, raw=True)

    if any(w in t for w in WOMEN_WORDS):
        is_widow_query = any(w in t for w in ["widow", "vidhwa", "विधवा"])
        matches = [s for s in SCHEMES if "female" in s["eligibility"]
                  and (not is_widow_query or "widow" in s["name"].lower())]
        if matches:
            block = "\n\n".join(_format_scheme(s, lang) for s in matches)
            return _reply(block, block, lang, raw=True)

    if any(w in t for w in ELDERLY_WORDS):
        scheme = next((s for s in SCHEMES if s["name"] == "Old Age Pension"), None)
        if scheme:
            block = _format_scheme(scheme, lang)
            return _reply(block, block, lang, raw=True)

    return _reply(
        "I didn't quite catch that. Try asking about a specific scheme name "
        "(e.g. \"PM Awas Yojana\"), a department (e.g. \"agriculture schemes\"), "
        "who qualifies (e.g. \"schemes for farmers\"), or the project roadmap.",
        "मुझे ठीक से समझ नहीं आया। किसी योजना का नाम (जैसे \"PM आवास योजना\"), "
        "किसी विभाग (जैसे \"कृषि योजनाएं\"), कौन पात्र है (जैसे \"किसानों के लिए योजना\"), "
        "या प्रोजेक्ट रोडमैप के बारे में पूछकर देखें।", lang)


def _reply(text_en, text_hi, lang, raw=False):
    text = text_hi if lang == "hi" else text_en
    return {"lang": lang, "text": text}
