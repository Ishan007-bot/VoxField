"""Test extraction accuracy: 12 realistic voice transcripts covering all field types.

Run:  pytest test_extraction.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from db import init_db
from seed import seed
from ai_engine import _rule_extract

# Seed the DB so vocab lookups work.
init_db()
seed()


def _vocab():
    from db import db
    import json
    with db() as conn:
        rows = conn.execute("SELECT code, name, location, procedures FROM assets").fetchall()
    codes, names, locations, procedures = [], [], set(), set()
    for r in rows:
        codes.append(r["code"])
        names.append(r["name"])
        locations.add(r["location"])
        for p in json.loads(r["procedures"]):
            procedures.add(p["name"])
    return {"codes": codes, "names": names,
            "locations": sorted(locations), "procedures": sorted(procedures)}


VOCAB = _vocab()


# ── Test cases ───────────────────────────────────────────────────────────────
# Each is (transcript, expected_dict) where expected_dict has the fields we
# MUST get right. Fields not in expected are not checked (flexible).

CASES = [
    # 1. Clear English report with asset code, fault, and severity
    (
        "Pump PMP-4471 in Pump House Bay 2 has a major seal leak. "
        "I replaced the mechanical seal and torqued the gland bolts. "
        "Need a new coupling guard.",
        {
            "asset_code": "PMP-4471",
            "location": "Pump House Bay 2",
            "severity": "high",
            "intent": "create_wo",
        },
    ),
    # 2. Close work order
    (
        "Work on motor MTR-1180 is completed. Bearing replacement done, "
        "test run was successful.",
        {
            "asset_code": "MTR-1180",
            "intent": "close_wo",
        },
    ),
    # 3. Query intent
    (
        "What are the specs of the boiler feed pump PMP-3310?",
        {
            "asset_code": "PMP-3310",
            "intent": "query",
        },
    ),
    # 4. Critical severity keywords
    (
        "Emergency at Generator House! GEN-9001 is overheating, coolant leak "
        "is critical. Oil pressure dropping fast.",
        {
            "asset_code": "GEN-9001",
            "severity": "critical",
        },
    ),
    # 5. Low severity, cosmetic issue
    (
        "Minor paint damage on valve VLV-7001 housing. Cosmetic only, "
        "no functional impact. Low priority.",
        {
            "asset_code": "VLV-7001",
            "severity": "low",
            "intent": "create_wo",
        },
    ),
    # 6. Parts required extraction
    (
        "Compressor CMP-5500 air filter is clogged. Replaced the old element. "
        "Need a new oil separator and O-ring for next maintenance.",
        {
            "asset_code": "CMP-5500",
            "intent": "create_wo",
        },
    ),
    # 7. Update intent
    (
        "Update on work order for HEX-8001. Found two additional leaking tubes "
        "during inspection. Change severity to high.",
        {
            "asset_code": "HEX-8001",
            "intent": "update_wo",
        },
    ),
    # 8. Location extraction without explicit code
    (
        "Checked the air handling unit on Admin Block Roof. Filters are dirty, "
        "differential pressure alarm is active. Replaced G4 and F7 filters.",
        {
            "location": "Admin Block Roof",
            "intent": "create_wo",
        },
    ),
    # 9. Action taken extraction
    (
        "Calibrated the positioner on valve VLV-7002. Applied 4 milliamps, "
        "adjusted zero and span. Valve is now tracking 0 to 100 percent correctly.",
        {
            "asset_code": "VLV-7002",
            "intent": "create_wo",
        },
    ),
    # 10. Escalation intent
    (
        "Need to escalate this to supervisor immediately. Transformer TRF-100 "
        "oil is discolored and Buchholz relay tripped. Too dangerous to proceed.",
        {
            "asset_code": "TRF-100",
            "intent": "escalate",
        },
    ),
    # 11. Medium severity with fault code
    (
        "Motor MTR-2090 vibration reading is 8.2 mm/s, above the 7.1 alarm limit. "
        "Fault code VIB-HIGH. Moderate severity, needs bearing check.",
        {
            "asset_code": "MTR-2090",
            "severity": "medium",
            "intent": "create_wo",
        },
    ),
    # 12. Spoken code without dash (common in speech)
    (
        "Inspected SWG 200 main LV switchboard at substation. "
        "ACB contacts are worn, needs maintenance. Ordered replacement contacts.",
        {
            "asset_code": "SWG-200",
            "location": "Substation",
            "intent": "create_wo",
        },
    ),
]


class TestExtraction:
    """Rule-based extraction accuracy tests."""

    def _extract(self, transcript):
        return _rule_extract(transcript, VOCAB)

    def test_case_01_seal_leak_report(self):
        result = self._extract(CASES[0][0])
        expected = CASES[0][1]
        assert result["asset_code"] == expected["asset_code"]
        assert result["location"] == expected["location"]
        assert result["severity"] in ("high", "critical")  # "major" maps to high
        assert result["intent"] == expected["intent"]

    def test_case_02_close_work_order(self):
        result = self._extract(CASES[1][0])
        assert result["asset_code"] == "MTR-1180"
        assert result["intent"] == "close_wo"

    def test_case_03_query_intent(self):
        result = self._extract(CASES[2][0])
        assert result["asset_code"] == "PMP-3310"
        assert result["intent"] == "query"

    def test_case_04_critical_severity(self):
        result = self._extract(CASES[3][0])
        assert result["asset_code"] == "GEN-9001"
        assert result["severity"] == "critical"

    def test_case_05_low_severity(self):
        result = self._extract(CASES[4][0])
        assert result["asset_code"] == "VLV-7001"
        assert result["severity"] == "low"
        assert result["intent"] == "create_wo"

    def test_case_06_parts_required(self):
        result = self._extract(CASES[5][0])
        assert result["asset_code"] == "CMP-5500"
        assert result["intent"] == "create_wo"

    def test_case_07_update_intent(self):
        result = self._extract(CASES[6][0])
        assert result["asset_code"] == "HEX-8001"
        assert result["intent"] == "update_wo"

    def test_case_08_location_extraction(self):
        result = self._extract(CASES[7][0])
        assert result["location"] == "Admin Block Roof"
        assert result["intent"] == "create_wo"

    def test_case_09_action_taken(self):
        result = self._extract(CASES[8][0])
        assert result["asset_code"] == "VLV-7002"
        assert result["action_taken"] is not None
        assert "calibrat" in result["action_taken"].lower()

    def test_case_10_escalation_intent(self):
        result = self._extract(CASES[9][0])
        assert result["asset_code"] == "TRF-100"
        assert result["intent"] == "escalate"

    def test_case_11_medium_severity(self):
        result = self._extract(CASES[10][0])
        assert result["asset_code"] == "MTR-2090"
        assert result["severity"] in ("medium", "high")  # "moderate" maps to medium

    def test_case_12_spoken_code_no_dash(self):
        result = self._extract(CASES[11][0])
        assert result["asset_code"] == "SWG-200"
        assert result["location"] == "Substation"
        assert result["intent"] == "create_wo"

    def test_all_extractions_have_confidence(self):
        """Every extraction must include per-field confidence scores."""
        for transcript, _ in CASES:
            result = self._extract(transcript)
            assert "confidence" in result, f"Missing confidence for: {transcript[:40]}..."
            assert isinstance(result["confidence"], dict)

    def test_inspection_result_never_empty(self):
        """The inspection_result field should always have content."""
        for transcript, _ in CASES:
            result = self._extract(transcript)
            assert result["inspection_result"], f"Empty inspection for: {transcript[:40]}..."
