"""API endpoint tests for VoxField backend.

Run:  pytest test_api.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pytest
from fastapi.testclient import TestClient

# Ensure a clean test DB
TEST_DB = os.path.join(os.path.dirname(__file__), "test_field_assistant.db")
os.environ.setdefault("VOXFIELD_DB", TEST_DB)

from main import app

client = TestClient(app)


class TestHealthAndStatus:
    def test_root(self):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["app"] == "VoxField"
        assert data["status"] == "ok"

    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["assets"] > 0

    def test_ai_status(self):
        r = client.get("/ai-status")
        assert r.status_code == 200
        data = r.json()
        assert "engine" in data
        assert "backend" in data  # which LLM backend is live

    def test_speech_status(self):
        r = client.get("/speech-status")
        assert r.status_code == 200
        assert "cloud_speech" in r.json()


class TestAssets:
    def test_list_assets(self):
        r = client.get("/assets")
        assert r.status_code == 200
        assets = r.json()
        assert len(assets) >= 30  # seeded with ~40 assets
        assert "code" in assets[0]
        assert "specs" in assets[0]

    def test_list_assets_by_type(self):
        r = client.get("/assets?type=Pump")
        assert r.status_code == 200
        pumps = r.json()
        assert all(a["type"] == "Pump" for a in pumps)

    def test_get_single_asset(self):
        r = client.get("/assets/PMP-4471")
        assert r.status_code == 200
        asset = r.json()
        assert asset["code"] == "PMP-4471"
        assert "maintenance_history" in asset

    def test_get_missing_asset(self):
        r = client.get("/assets/FAKE-9999")
        assert r.status_code == 404

    def test_asset_types(self):
        r = client.get("/asset-types")
        assert r.status_code == 200
        types = r.json()
        assert len(types) >= 6
        assert all("type" in t and "count" in t for t in types)

    def test_vocabulary(self):
        r = client.get("/vocabulary")
        assert r.status_code == 200
        v = r.json()
        assert "codes" in v and "names" in v
        assert "PMP-4471" in v["codes"]


class TestExtraction:
    def test_extract_basic(self):
        r = client.post("/extract", json={
            "transcript": "Pump PMP-4471 has a major seal leak in Pump House Bay 2",
            "technician": "Test Tech",
        })
        assert r.status_code == 200
        data = r.json()
        assert "fields" in data
        assert "confidence" in data
        assert "engine" in data
        assert "elapsed_ms" in data
        assert data["fields"]["asset_code"] == "PMP-4471"

    def test_extract_includes_confidence(self):
        r = client.post("/extract", json={
            "transcript": "Minor issue on valve VLV-7001, low priority cosmetic damage",
        })
        data = r.json()
        conf = data["confidence"]
        assert isinstance(conf, dict)
        assert "asset_code" in conf
        assert "severity" in conf

    def test_extract_escalation_intent(self):
        r = client.post("/extract", json={
            "transcript": "Escalate to supervisor, transformer TRF-100 Buchholz relay tripped, too dangerous",
        })
        data = r.json()
        assert data["fields"]["intent"] == "escalate"


class TestQuery:
    def test_query_basic(self):
        r = client.post("/query", json={
            "question": "What are the specs of pump PMP-4471?",
            "technician": "Test Tech",
        })
        assert r.status_code == 200
        data = r.json()
        assert "answer" in data
        assert "elapsed_ms" in data
        assert data["asset_code"] == "PMP-4471"
        assert "retrieval" in data

    def test_query_response_time(self):
        """Success metric: voice query returns answer within 3 seconds."""
        r = client.post("/query", json={
            "question": "When was the last maintenance on GEN-9001?",
        })
        data = r.json()
        assert data["elapsed_ms"] < 3000, f"Query took {data['elapsed_ms']}ms, exceeds 3s target"

    def test_query_no_match(self):
        r = client.post("/query", json={
            "question": "Tell me about the quantum flux capacitor",
        })
        assert r.status_code == 200  # should not error, just give a best-effort answer


class TestWorkOrders:
    def test_create_work_order(self):
        r = client.post("/work-orders", json={
            "asset_code": "PMP-4471",
            "inspection_result": "Seal leak detected",
            "severity": "high",
            "location": "Pump House Bay 2",
            "technician": "Test Tech",
            "raw_transcript": "Pump PMP-4471 has a seal leak",
        })
        assert r.status_code == 200
        data = r.json()
        assert "work_order" in data
        assert "confirmation" in data
        wo = data["work_order"]
        assert wo["asset_code"] == "PMP-4471"
        assert wo["status"] == "open"
        return wo["id"]

    def test_list_work_orders(self):
        r = client.get("/work-orders")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_update_work_order(self):
        # Create one first
        cr = client.post("/work-orders", json={
            "asset_code": "MTR-1180",
            "inspection_result": "Vibration high",
            "severity": "medium",
            "technician": "Test Tech",
        })
        wo_id = cr.json()["work_order"]["id"]

        r = client.patch(f"/work-orders/{wo_id}", json={"severity": "high"})
        assert r.status_code == 200
        assert r.json()["work_order"]["severity"] == "high"

    def test_close_work_order(self):
        cr = client.post("/work-orders", json={
            "asset_code": "VLV-7001",
            "inspection_result": "Test close",
            "technician": "Test Tech",
        })
        wo_id = cr.json()["work_order"]["id"]

        r = client.post(f"/work-orders/{wo_id}/close")
        assert r.status_code == 200
        assert r.json()["work_order"]["status"] == "closed"

    def test_work_order_correctly_structured(self):
        """Success metric: work order by voice results in correctly structured record."""
        r = client.post("/work-orders", json={
            "asset_code": "CMP-5500",
            "inspection_result": "Air filter clogged, replaced",
            "fault_code": "FILT-01",
            "location": "Compressor Room",
            "severity": "medium",
            "action_taken": "Replaced air filter element",
            "parts_required": "Oil separator, O-ring",
            "technician": "R. Mehta",
            "raw_transcript": "Compressor CMP-5500 air filter clogged replaced element need new oil separator and O-ring",
        })
        wo = r.json()["work_order"]
        required_fields = ["id", "asset_code", "inspection_result", "fault_code",
                          "location", "severity", "action_taken", "parts_required",
                          "status", "raw_transcript", "technician", "created_at"]
        for f in required_fields:
            assert f in wo, f"Missing field: {f}"
        assert wo["status"] == "open"


class TestEscalations:
    def test_create_escalation(self):
        r = client.post("/escalations", json={
            "asset_code": "TRF-100",
            "reason": "Buchholz relay tripped, oil discolored",
            "location": "Substation",
            "severity": "critical",
            "technician": "R. Mehta",
        })
        assert r.status_code == 200
        data = r.json()
        assert "escalation_id" in data
        assert "confirmation" in data

    def test_list_escalations(self):
        r = client.get("/escalations")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_acknowledge_escalation(self):
        cr = client.post("/escalations", json={
            "asset_code": "GEN-9001",
            "reason": "Overheating",
            "technician": "Test Tech",
        })
        esc_id = cr.json()["escalation_id"]

        r = client.patch(f"/escalations/{esc_id}?status=acknowledged")
        assert r.status_code == 200
        assert r.json()["status"] == "acknowledged"


class TestDashboard:
    def test_dashboard(self):
        r = client.get("/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "stats" in data
        assert "work_orders" in data
        assert "transcripts" in data
        assert "alerts" in data
        assert "escalations" in data
        assert "timeline" in data
        assert "severity_chart" in data
        # Stats fields
        s = data["stats"]
        assert "assets" in s
        assert "open_work_orders" in s
        assert "escalations_open" in s

    def test_stats(self):
        r = client.get("/stats")
        assert r.status_code == 200
        s = r.json()
        assert "assets" in s and "open_work_orders" in s


class TestActivity:
    def test_activity_feed(self):
        # First create some activity
        client.post("/extract", json={"transcript": "Test note for activity"})
        r = client.get("/activity?limit=5")
        assert r.status_code == 200
        notes = r.json()
        assert len(notes) > 0
        assert "transcript" in notes[0]

    def test_delete_voice_note(self):
        client.post("/extract", json={"transcript": "Note to delete"})
        notes = client.get("/activity?limit=1").json()
        if notes:
            r = client.delete(f"/voice-notes/{notes[0]['id']}")
            assert r.status_code == 200

    def test_clear_voice_notes(self):
        r = client.delete("/voice-notes")
        assert r.status_code == 200
        assert "cleared" in r.json()
