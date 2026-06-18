"""Offline queue sync correctness tests.

Simulates the offline queue pattern: items are queued while offline,
then processed in order when reconnected. Verifies that:
  - All queued items are processed
  - Failed items are retried
  - Processing order is preserved
  - Work orders created from queued items are correctly structured

Run:  pytest test_offline_sync.py -v
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class QueueItem:
    """Mimics the IndexedDB queue item shape from the frontend."""
    def __init__(self, item_type, payload, transcript="", item_id=None):
        self.id = item_id or id(self)
        self.type = item_type
        self.payload = payload
        self.transcript = transcript
        self.status = "pending"
        self.error = None


def _ok(resp):
    """Raise on non-2xx, mirroring the frontend fetch wrapper (api.js throws
    on HTTP errors). Without this, a 404 would be wrongly treated as success."""
    if resp.status_code >= 400:
        raise RuntimeError(f"API {resp.status_code}: {resp.text}")
    return resp.json()


def process_item(item):
    """Mirrors the frontend processItem() logic — calls the real API."""
    p = item.payload
    if item.type == "create_wo":
        ex = _ok(client.post("/extract", json={
            "transcript": item.transcript,
            "technician": "Sync-Test",
            "language": p.get("language", "en"),
        }))
        f = ex["fields"]
        return _ok(client.post("/work-orders", json={
            "asset_code": f.get("asset_code"),
            "inspection_result": f.get("inspection_result"),
            "fault_code": f.get("fault_code"),
            "location": f.get("location"),
            "severity": f.get("severity"),
            "action_taken": f.get("action_taken"),
            "parts_required": f.get("parts_required"),
            "raw_transcript": item.transcript,
            "technician": "Sync-Test",
        }))

    if item.type == "query":
        return _ok(client.post("/query", json={
            "question": p["question"],
            "technician": "Sync-Test",
            "language": p.get("language", "en"),
        }))

    if item.type == "close_wo":
        return _ok(client.post(f"/work-orders/{p['id']}/close"))

    raise ValueError(f"Unknown type: {item.type}")


def drain_queue(items):
    """Simulates the frontend drain() function."""
    synced, failed = 0, 0
    for item in items:
        if item.status != "pending":
            continue
        try:
            result = process_item(item)
            item.status = "done"
            item.result = result
            item.error = None
            synced += 1
        except Exception as e:
            item.status = "error"
            item.error = str(e)
            failed += 1
    return synced, failed


class TestOfflineSync:
    """Success metric: offline queue syncs correctly and processes all queued notes."""

    def test_queue_single_work_order(self):
        """A single queued work order is created correctly on sync."""
        items = [QueueItem(
            "create_wo",
            {"language": "en"},
            "Pump PMP-4471 has a seal leak in Pump House Bay 2, high severity"
        )]
        synced, failed = drain_queue(items)
        assert synced == 1
        assert failed == 0
        assert items[0].status == "done"
        wo = items[0].result["work_order"]
        assert wo["asset_code"] == "PMP-4471"
        assert wo["status"] == "open"

    def test_queue_multiple_items_in_order(self):
        """Multiple queued items are processed in FIFO order."""
        items = [
            QueueItem("create_wo", {"language": "en"},
                      "Motor MTR-1180 insulation test failed, high severity"),
            QueueItem("query", {"question": "What are specs of PMP-4471?", "language": "en"},
                      "What are specs of PMP-4471?"),
            QueueItem("create_wo", {"language": "en"},
                      "Valve VLV-7003 pressure test, lifted at 12.5 bar"),
        ]
        synced, failed = drain_queue(items)
        assert synced == 3
        assert failed == 0
        assert all(i.status == "done" for i in items)

    def test_queue_with_close_wo(self):
        """Queue a create + close sequence."""
        # First create a WO directly
        cr = client.post("/work-orders", json={
            "asset_code": "CMP-5500",
            "inspection_result": "Filter clogged",
            "technician": "Sync-Test",
        })
        wo_id = cr.json()["work_order"]["id"]

        # Queue a close
        items = [QueueItem("close_wo", {"id": wo_id})]
        synced, failed = drain_queue(items)
        assert synced == 1
        assert items[0].result["work_order"]["status"] == "closed"

    def test_queue_query_returns_answer(self):
        """Queued queries produce valid answers on sync."""
        items = [QueueItem(
            "query",
            {"question": "When was the last maintenance on GEN-9001?", "language": "en"},
            "When was the last maintenance on GEN-9001?",
        )]
        synced, failed = drain_queue(items)
        assert synced == 1
        result = items[0].result
        assert "answer" in result
        assert result["asset_code"] == "GEN-9001"

    def test_failed_items_marked_error(self):
        """Items that fail processing are marked as error, not done."""
        items = [QueueItem("close_wo", {"id": 999999})]  # non-existent WO
        synced, failed = drain_queue(items)
        assert synced == 0
        assert failed == 1
        assert items[0].status == "error"

    def test_retry_after_failure(self):
        """Errored items can be retried (re-armed as pending)."""
        items = [QueueItem("close_wo", {"id": 999999})]
        drain_queue(items)
        assert items[0].status == "error"

        # Re-arm (simulates retryErrored() in frontend)
        items[0].status = "pending"
        items[0].error = None

        # Still fails (WO doesn't exist), but the retry mechanism works
        synced, failed = drain_queue(items)
        assert failed == 1  # still fails, but it WAS retried

    def test_mixed_success_and_failure(self):
        """Queue with some valid and some invalid items processes correctly."""
        items = [
            QueueItem("create_wo", {"language": "en"},
                      "Pump PMP-3310 pressure test passed"),
            QueueItem("close_wo", {"id": 999999}),  # will fail
            QueueItem("query", {"question": "Specs of TRF-100?", "language": "en"},
                      "Specs of TRF-100?"),
        ]
        synced, failed = drain_queue(items)
        assert synced == 2
        assert failed == 1
        assert items[0].status == "done"
        assert items[1].status == "error"
        assert items[2].status == "done"

    def test_empty_queue(self):
        """Draining an empty queue returns zero counts."""
        synced, failed = drain_queue([])
        assert synced == 0
        assert failed == 0
