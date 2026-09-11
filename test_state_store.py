#!/usr/bin/env python3
"""
Tests for the state store's failure handling. No network - `requests` is
stubbed.

    python3 -m unittest test_state_store -v

The property under test is one-directional: it is fine to fail loudly, and
never acceptable to report "no position" when one might be held. That mistake
makes the bot buy again while already holding, and never sell what it holds.
"""

import os
import tempfile
import unittest

os.environ["BLOB_READ_WRITE_TOKEN"] = "vercel_blob_rw_teststore_secret"
os.environ["BOT_BLOB_PATHNAME"] = "test/state.db"

import state_store  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, content=b"", payload=None):
        self.status_code = status_code
        self.content = content
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class StateStoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        os.environ["BOT_DB_PATH"] = self.tmp.name
        self.get_calls = []
        self._real_get = state_store.requests.get
        state_store._RETRY_SLEEP = 0  # don't actually sleep in tests
        state_store.requests.get = self.fake_get

    def tearDown(self):
        state_store.requests.get = self._real_get
        os.path.exists(self.tmp.name) and os.remove(self.tmp.name)

    def fake_get(self, url, **kwargs):
        """Route object reads vs list calls the way the real API does."""
        is_list = "prefix" in kwargs.get("params", {})
        self.get_calls.append("list" if is_list else "read")
        if is_list:
            return FakeResponse(200, payload=self.list_payload)
        return self.read_responses.pop(0) if self.read_responses else FakeResponse(404)


class TestTransient404(StateStoreTestCase):
    """A 404 for an object that exists must never read as 'no position'."""

    def test_retries_and_succeeds_when_404_is_transient(self):
        import sqlite3
        # Build a real SQLite file to hand back on the retry.
        path = self.tmp.name
        conn = sqlite3.connect(path)
        conn.execute("create table if not exists bot_state "
                     "(key text primary key, value text, updated_at text)")
        conn.execute("insert into bot_state values ('k', '{\"volume\": 2.0, "
                     "\"entry\": 50.0}', 'now')")
        conn.commit(); conn.close()
        with open(path, "rb") as f:
            blob_bytes = f.read()

        self.list_payload = {"blobs": [{"pathname": "test/state.db"}]}
        self.read_responses = [FakeResponse(404), FakeResponse(200, blob_bytes)]

        self.assertEqual(state_store.load_position("k"),
                         {"volume": 2.0, "entry": 50.0})
        self.assertIn("list", self.get_calls)

    def test_raises_when_404_persists_for_an_existing_object(self):
        self.list_payload = {"blobs": [{"pathname": "test/state.db"}]}
        self.read_responses = []  # every read 404s
        with self.assertRaises(RuntimeError) as ctx:
            state_store.load_position("k")
        self.assertIn("refusing to assume", str(ctx.exception))

    def test_genuinely_absent_object_reads_as_no_position(self):
        """First run: nothing stored yet is a legitimate empty state."""
        self.list_payload = {"blobs": []}
        self.read_responses = []
        self.assertIsNone(state_store.load_position("k"))

    def test_unrelated_prefix_match_does_not_count_as_existing(self):
        """list uses a prefix, so a longer path must not be mistaken for ours."""
        self.list_payload = {"blobs": [{"pathname": "test/state.db.backup"}]}
        self.read_responses = []
        self.assertIsNone(state_store.load_position("k"))

    def test_server_error_raises_rather_than_reporting_flat(self):
        self.list_payload = {"blobs": []}
        self.read_responses = [FakeResponse(500)]
        with self.assertRaises(RuntimeError):
            state_store.load_position("k")


if __name__ == "__main__":
    unittest.main()
