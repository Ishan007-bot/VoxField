"""Knowledge-base retrieval: given a question, find the most relevant asset(s)
and pull together specs, history, and procedures as context for the Q&A engine.

Retrieval is intentionally simple and fast (no embeddings server needed):
  1. Try to spot an explicit asset code in the text (e.g. "PMP-4471").
  2. Otherwise fuzzy-match asset names / types / locations with rapidfuzz.
This keeps Q&A well under the 3-second target even on the rule-based path.
"""
import json
import re
from rapidfuzz import fuzz, process

from db import db

# Matches codes like PMP-4471, HEX-8001, SWG-200, TRF-100, etc.
CODE_RE = re.compile(r"\b([A-Z]{2,4})[\s-]?(\d{2,4})\b", re.IGNORECASE)


def _all_assets():
    with db() as conn:
        rows = conn.execute("SELECT * FROM assets").fetchall()
    return [dict(r) for r in rows]


def _normalize_code(raw_prefix, raw_num):
    return f"{raw_prefix.upper()}-{raw_num}"


def find_asset(text):
    """Return the single best-matching asset dict for a query, or None."""
    assets = _all_assets()
    if not assets:
        return None

    by_code = {a["code"].upper(): a for a in assets}

    # 1) Explicit code mention — strongest signal.
    for m in CODE_RE.finditer(text or ""):
        candidate = _normalize_code(m.group(1), m.group(2))
        if candidate in by_code:
            return by_code[candidate]
        # spoken codes sometimes drop the dash or mangle spacing — try loose match
        loose = candidate.replace("-", "")
        for code, a in by_code.items():
            if code.replace("-", "") == loose:
                return a

    # 2) Fuzzy match against names (and fall back to type + location).
    names = {a["name"]: a for a in assets}
    best = process.extractOne(text, names.keys(), scorer=fuzz.partial_ratio)
    if best and best[1] >= 75:
        return names[best[0]]

    # 3) Match by asset type keyword (e.g. "the boiler feed pump", "a transformer").
    lowered = (text or "").lower()
    for a in assets:
        if a["type"].lower() in lowered or a["name"].lower() in lowered:
            return a

    # 4) Last resort: best name match even if weak, so we have *something*.
    if best and best[1] >= 50:
        return names[best[0]]
    return None


def asset_context(asset):
    """Build a compact, readable context block + structured data for one asset."""
    with db() as conn:
        history = conn.execute(
            "SELECT date, summary, technician FROM maintenance_history "
            "WHERE asset_code = ? ORDER BY date DESC",
            (asset["code"],),
        ).fetchall()

    specs = json.loads(asset["specs"])
    procedures = json.loads(asset["procedures"])
    history = [dict(h) for h in history]

    lines = [
        f"Asset code: {asset['code']}",
        f"Name: {asset['name']}",
        f"Type: {asset['type']}",
        f"Location: {asset['location']}",
        "Specifications:",
    ]
    for k, v in specs.items():
        lines.append(f"  - {k.replace('_', ' ')}: {v}")

    lines.append("Procedures:")
    for p in procedures:
        lines.append(f"  - {p['name']}:")
        for i, step in enumerate(p["steps"], 1):
            lines.append(f"      {i}. {step}")

    lines.append("Maintenance history (most recent first):")
    if history:
        for h in history:
            lines.append(f"  - {h['date']} ({h['technician']}): {h['summary']}")
    else:
        lines.append("  - No recorded maintenance history.")

    return {
        "text": "\n".join(lines),
        "asset": {**asset, "specs": specs, "procedures": procedures},
        "history": history,
    }


def retrieve(question):
    """Return context for the asset most relevant to the question (or None)."""
    asset = find_asset(question)
    if not asset:
        return None
    return asset_context(asset)
