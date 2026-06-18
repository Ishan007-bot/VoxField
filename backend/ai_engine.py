"""AI engine for VoxField.

Two capabilities, one interface:
  - extract(transcript, vocab)  -> structured work-order fields (6 fields)
  - answer(question, context)   -> natural-language answer (same language in)

Each tries **Gemini** first (if a key is configured and the call succeeds) and
falls back to a **rule-based** implementation that needs no network. This makes
the app fully functional offline / without an API key, just with lower quality.
"""
import json
import os
import re

from dotenv import load_dotenv

load_dotenv()  # read backend/.env

# ── Config ──────────────────────────────────────────────────────────────────
# Two possible LLM backends, tried in this order, then rule-based fallback:
#   1. Vertex AI  (service-account JSON) — when USE_VERTEX=true
#   2. AI Studio  (GEMINI_API_KEY)       — when a key is set
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

USE_VERTEX = os.getenv("USE_VERTEX", "false").strip().lower() == "true"
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1").strip()
VERTEX_MODEL = os.getenv("VERTEX_MODEL", "gemini-2.5-flash").strip()
_CRED_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
# Resolve a relative credentials path against the backend dir for convenience.
if _CRED_PATH and not os.path.isabs(_CRED_PATH):
    _CRED_PATH = os.path.join(os.path.dirname(__file__), _CRED_PATH)

_backend = None        # "vertex" | "studio" | None — which LLM is live
_model = None          # the model client object
_init_error = None


def _project_id_from_creds():
    try:
        with open(_CRED_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("project_id")
    except Exception:
        return None


def _init_llm():
    """Lazily initialise the best available LLM backend. Idempotent."""
    global _backend, _model, _init_error
    if _backend is not None or _init_error is not None:
        return _backend

    # 1) Vertex AI via service-account JSON
    if USE_VERTEX and _CRED_PATH and os.path.exists(_CRED_PATH):
        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _CRED_PATH
            import vertexai
            from vertexai.generative_models import GenerativeModel
            project = _project_id_from_creds()
            vertexai.init(project=project, location=VERTEX_LOCATION)
            _model = GenerativeModel(VERTEX_MODEL)
            _backend = "vertex"
            return _backend
        except Exception as e:
            _init_error = f"vertex: {e}"

    # 2) AI Studio key
    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            _model = genai.GenerativeModel(GEMINI_MODEL)
            _backend = "studio"
            return _backend
        except Exception as e:
            _init_error = f"studio: {e}"

    return None


def gemini_available():
    return _init_llm() is not None


def llm_backend():
    """Returns 'vertex', 'studio', or None — for /ai-status reporting."""
    return _init_llm()


# Fail fast when the LLM is throttled/unreachable so we fall back to rule-based
# quickly instead of the SDK's long retry storm.
def _generate(prompt):
    backend = _init_llm()
    if backend is None:
        raise RuntimeError("no LLM backend available")
    if backend == "studio":
        from google.api_core import retry as _retry
        return _model.generate_content(
            prompt,
            request_options={"timeout": 12, "retry": _retry.Retry(deadline=12, maximum=0)},
        )
    # Vertex AI client
    return _model.generate_content(prompt)


SEVERITY_WORDS = {
    "critical": ["critical", "catastrophic", "emergency", "explosion", "fire", "danger"],
    "high": ["high", "severe", "major", "urgent", "bad", "serious", "heavy"],
    "medium": ["medium", "moderate", "noticeable"],
    "low": ["low", "minor", "small", "slight", "cosmetic"],
}

FIELDS = ["inspection_result", "fault_code", "location", "severity",
          "action_taken", "parts_required", "asset_code", "intent"]

ESCALATION_WORDS = ["escalate", "escalation", "escalate to", "escalate two",
                    "estimate the supervisor", "estimate to supervisor",
                    "supervisor", "manager", "urgent help",
                    "need backup", "send help", "emergency", "critical failure",
                    "cannot handle", "too dangerous", "safety issue", "hazard",
                    "send supervisor", "call supervisor", "get supervisor",
                    "need supervisor", "alert supervisor"]


# ---------------------------------------------------------------------------
# EXTRACTION
# ---------------------------------------------------------------------------
def _extract_prompt(transcript, vocab):
    codes = ", ".join(vocab.get("codes", [])[:80])
    procs = ", ".join(vocab.get("procedures", [])[:60])
    locs = ", ".join(vocab.get("locations", []))
    return f"""You are a maintenance work-order extraction engine for industrial field technicians.
A technician dictated a voice note (it may be in English, Hindi, or Spanish, and may be messy).
Convert it into a structured work-order JSON object.

Known equipment codes: {codes}
Known procedures: {procs}
Known locations: {locs}

Return ONLY a JSON object with EXACTLY these keys (use null if truly not mentioned):
  "intent": one of "create_wo", "update_wo", "close_wo", "query", "escalate", "note"
  "asset_code": the equipment code mentioned, normalised like "PMP-4471", or null
  "inspection_result": short summary of what was found / the condition observed
  "fault_code": any fault/error code or short fault label, or null
  "location": where the work is, prefer a known location, else what was said
  "severity": one of "low", "medium", "high", "critical" based on the note
  "action_taken": what the technician did, or null if nothing done yet
  "parts_required": comma-separated parts needed, or null
  "confidence": a dict with per-field confidence: {{"asset_code": 0.0-1.0, "severity": 0.0-1.0, ...}} for all fields above

Voice note: \"\"\"{transcript}\"\"\"

JSON:"""


def _rule_extract(transcript, vocab):
    """Regex/keyword fallback. Decent for clear English notes."""
    text = transcript or ""
    low = text.lower()
    result = {k: None for k in FIELDS}

    # asset code
    m = re.search(r"\b([A-Za-z]{2,4})[\s-]?(\d{2,4})\b", text)
    if m:
        code = f"{m.group(1).upper()}-{m.group(2)}"
        if code in vocab.get("codes", []):
            result["asset_code"] = code
        else:
            # loose match against known codes
            stripped = code.replace("-", "")
            for c in vocab.get("codes", []):
                if c.replace("-", "") == stripped:
                    result["asset_code"] = c
                    break

    # location: prefer a known location appearing in the text
    for loc in vocab.get("locations", []):
        if loc.lower() in low:
            result["location"] = loc
            break

    # severity
    for level, words in SEVERITY_WORDS.items():
        if any(w in low for w in words):
            result["severity"] = level
            break
    if result["severity"] is None and ("leak" in low or "fault" in low or "fail" in low):
        result["severity"] = "medium"

    # action taken — start from the EARLIEST action verb mentioned in the text
    # (not the first one in this list), so "Calibrated ... adjusted ..." captures
    # the calibration, not the later adjustment.
    action_verbs = ["replaced", "repaired", "cleaned", "tightened", "adjusted",
                    "lubricated", "reset", "topped up", "swapped", "fixed", "calibrated"]
    positions = [low.find(v) for v in action_verbs if v in low]
    if positions:
        idx = min(positions)
        result["action_taken"] = text[idx:idx + 80].strip().rstrip(".")

    # parts required
    pm = re.search(r"(?:need|needs|require[sd]?|order|new)\s+(?:a\s+|an\s+)?([\w\s,]+?)"
                   r"(?:\.|$|and then|then|also)", low)
    if pm:
        result["parts_required"] = pm.group(1).strip().rstrip(".")

    # inspection result = the leading sentence, trimmed
    result["inspection_result"] = re.split(r"[.;]", text.strip())[0][:140] or text[:140]

    # intent
    if any(w in low for w in ESCALATION_WORDS):
        result["intent"] = "escalate"
        result["severity"] = result["severity"] or "critical"
    elif any(w in low for w in ["close", "complete", "completed", "done", "finished"]):
        result["intent"] = "close_wo"
    elif any(w in low for w in ["update", "add to", "change"]):
        result["intent"] = "update_wo"
    elif text.strip().endswith("?") or low.startswith(("what", "how", "when", "where",
                                                        "which", "show", "tell", "list")):
        result["intent"] = "query"
    else:
        result["intent"] = "create_wo"

    # Per-field confidence (rule-based: binary — 1.0 if extracted, 0.0 if null)
    confidence = {}
    for k in FIELDS:
        if k == "intent":
            confidence[k] = 0.9  # intent detection is fairly reliable
        elif k == "confidence":
            continue
        else:
            confidence[k] = 1.0 if result.get(k) else 0.0
    result["confidence"] = confidence

    return result


def extract(transcript, vocab):
    """Extract structured work-order fields from a voice transcript.
    Returns (data_dict, engine_name)."""
    if gemini_available():
        try:
            resp = _generate(_extract_prompt(transcript, vocab))
            raw = (resp.text or "").strip()
            # strip ```json fences if present
            raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
            data = json.loads(raw)
            # ensure all expected keys exist
            for k in FIELDS:
                data.setdefault(k, None)
            # ensure confidence dict exists
            if "confidence" not in data or not isinstance(data.get("confidence"), dict):
                data["confidence"] = {k: (0.85 if data.get(k) else 0.0) for k in FIELDS if k != "confidence"}
            return data, "gemini"
        except Exception:
            pass  # fall through to rule-based
    return _rule_extract(transcript, vocab), "rule-based"


# ---------------------------------------------------------------------------
# QUERY / ANSWERING
# ---------------------------------------------------------------------------
def _answer_prompt(question, context_text):
    return f"""You are VoxField, a voice assistant for industrial field technicians.
Answer the technician's spoken question using ONLY the equipment data below.
Reply in the SAME language the question was asked in.
Keep it concise and natural for text-to-speech: 1-3 short sentences, no markdown,
no bullet symbols. If the data does not contain the answer, say you don't have
that information for this asset.

EQUIPMENT DATA:
{context_text}

QUESTION: {question}

ANSWER:"""


def _rule_answer(question, context):
    """Fallback answer: pick the relevant slice of the asset context."""
    if not context:
        return ("I couldn't find a matching asset for that question. "
                "Please mention the equipment code or name.")
    asset = context["asset"]
    low = question.lower()
    name = asset["name"]

    if any(w in low for w in ["spec", "rating", "power", "voltage", "flow", "capacity",
                              "pressure", "rpm", "size"]):
        specs = "; ".join(f"{k.replace('_',' ')} {v}" for k, v in asset["specs"].items())
        return f"{name} ({asset['code']}) specifications: {specs}."

    if any(w in low for w in ["history", "last", "previous", "maintenance", "serviced",
                              "repair", "done"]):
        if context["history"]:
            h = context["history"][0]
            return (f"The last maintenance on {name} was on {h['date']} by "
                    f"{h['technician']}: {h['summary']}")
        return f"There is no recorded maintenance history for {name}."

    if any(w in low for w in ["procedure", "step", "how do", "how to", "replace",
                              "test", "clean", "change"]):
        procs = asset["procedures"]
        if procs:
            p = procs[0]
            steps = " ".join(f"Step {i}: {s}" for i, s in enumerate(p["steps"], 1))
            return f"Procedure for {p['name']} on {name}. {steps}"
        return f"No procedures are recorded for {name}."

    if any(w in low for w in ["where", "location", "located"]):
        return f"{name} ({asset['code']}) is located at {asset['location']}."

    # generic
    return (f"{name} ({asset['code']}) is a {asset['type'].lower()} located at "
            f"{asset['location']}.")


def answer(question, context):
    """Answer a domain question from retrieved context.
    Returns (answer_text, engine_name)."""
    if gemini_available() and context is not None:
        try:
            resp = _generate(_answer_prompt(question, context["text"]))
            text = (resp.text or "").strip()
            if text:
                return text, "gemini"
        except Exception:
            pass
    return _rule_answer(question, context), "rule-based"
