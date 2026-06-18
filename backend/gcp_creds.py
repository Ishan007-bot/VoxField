"""Resolve the GCP service-account credentials path.

Works in two environments:
  - Local dev: GOOGLE_APPLICATION_CREDENTIALS points to gcp-credentials.json on disk.
  - Cloud (Render/etc.): the JSON is provided in the GCP_CREDENTIALS_JSON env var
    (pasting a file is fragile on most hosts). We write it to a temp file once and
    point Google's libraries at it.

Returns the resolved absolute path, or "" if no credentials are configured.
"""
import os
import json
import tempfile

_resolved = None


def credentials_path():
    global _resolved
    if _resolved is not None:
        return _resolved

    # 1) Inline JSON from an env var (cloud hosts) — highest priority.
    raw = os.getenv("GCP_CREDENTIALS_JSON", "").strip()
    if raw:
        try:
            json.loads(raw)  # validate it parses
            fd, path = tempfile.mkstemp(prefix="gcp-creds-", suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(raw)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
            _resolved = path
            return _resolved
        except Exception:
            pass  # fall through to file path

    # 2) File path (local dev).
    p = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if p and not os.path.isabs(p):
        p = os.path.join(os.path.dirname(__file__), p)
    _resolved = p if p and os.path.exists(p) else ""
    return _resolved


def project_id():
    """Read project_id from the resolved credentials file, or None."""
    path = credentials_path()
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("project_id")
    except Exception:
        return None
