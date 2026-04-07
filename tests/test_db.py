"""Tests for db.py -- SQLite session persistence."""

import os
import tempfile
import unittest

from shadow_code.db import Database, DatabaseError


class TestDatabase(unittest.TestCase):
    """Tests for the Database class using a temp file."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmpfile.close()
        self.db = Database(db_path=self.tmpfile.name)

    def tearDown(self):
        self.db.close()
        os.unlink(self.tmpfile.name)

    # --- Session CRUD ---

    def test_create_session(self):
        sid = self.db.create_session("test-model")
        self.assertIsInstance(sid, int)
        self.assertGreater(sid, 0)

    def test_create_session_with_name(self):
        sid = self.db.create_session("test-model", name="My Session")
        session = self.db.get_session(sid)
        self.assertEqual(session["name"], "My Session")

    def test_get_session(self):
        sid = self.db.create_session("test-model")
        session = self.db.get_session(sid)
        self.assertIsNotNone(session)
        self.assertEqual(session["id"], sid)
        self.assertEqual(session["model"], "test-model")
        self.assertIn("messages", session)
        self.assertEqual(len(session["messages"]), 0)

    def test_get_session_not_found(self):
        result = self.db.get_session(99999)
        self.assertIsNone(result)

    def test_delete_session(self):
        sid = self.db.create_session("test-model")
        self.assertTrue(self.db.delete_session(sid))
        self.assertIsNone(self.db.get_session(sid))

    def test_delete_session_not_found(self):
        self.assertFalse(self.db.delete_session(99999))

    def test_rename_session(self):
        sid = self.db.create_session("test-model")
        self.assertTrue(self.db.rename_session(sid, "Renamed"))
        session = self.db.get_session(sid)
        self.assertEqual(session["name"], "Renamed")

    def test_rename_session_not_found(self):
        self.assertFalse(self.db.rename_session(99999, "Nope"))

    # --- Messages ---

    def test_add_message(self):
        sid = self.db.create_session("test-model")
        self.db.add_message(sid, "user", "Hello")
        self.db.add_message(sid, "assistant", "Hi there!")
        session = self.db.get_session(sid)
        self.assertEqual(len(session["messages"]), 2)
        self.assertEqual(session["messages"][0]["role"], "user")
        self.assertEqual(session["messages"][0]["content"], "Hello")
        self.assertEqual(session["messages"][1]["role"], "assistant")

    def test_messages_ordered(self):
        sid = self.db.create_session("test-model")
        for i in range(5):
            self.db.add_message(sid, "user", f"msg {i}")
        session = self.db.get_session(sid)
        for i, msg in enumerate(session["messages"]):
            self.assertEqual(msg["content"], f"msg {i}")

    def test_message_has_timestamp(self):
        sid = self.db.create_session("test-model")
        self.db.add_message(sid, "user", "Hello")
        session = self.db.get_session(sid)
        self.assertIn("timestamp", session["messages"][0])
        self.assertGreater(len(session["messages"][0]["timestamp"]), 0)

    # --- Token tracking ---

    def test_update_tokens(self):
        sid = self.db.create_session("test-model")
        self.db.update_session_tokens(sid, 5000)
        session = self.db.get_session(sid)
        self.assertEqual(session["total_tokens"], 5000)

    # --- List sessions ---

    def test_list_sessions_empty(self):
        sessions = self.db.list_sessions()
        self.assertEqual(len(sessions), 0)

    def test_list_sessions(self):
        self.db.create_session("model-a")
        self.db.create_session("model-b")
        sessions = self.db.list_sessions()
        self.assertEqual(len(sessions), 2)

    def test_list_sessions_has_message_count(self):
        sid = self.db.create_session("test-model")
        self.db.add_message(sid, "user", "Hello")
        self.db.add_message(sid, "assistant", "Hi")
        sessions = self.db.list_sessions()
        self.assertEqual(sessions[0]["message_count"], 2)

    def test_list_sessions_limit(self):
        for i in range(10):
            self.db.create_session(f"model-{i}")
        sessions = self.db.list_sessions(limit=3)
        self.assertEqual(len(sessions), 3)

    # --- Context manager ---

    def test_context_manager(self):
        tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmpfile.close()
        try:
            with Database(db_path=tmpfile.name) as db:
                sid = db.create_session("ctx-model")
                self.assertGreater(sid, 0)
        finally:
            os.unlink(tmpfile.name)

    # --- Session metadata ---

    def test_session_has_timestamps(self):
        sid = self.db.create_session("test-model")
        session = self.db.get_session(sid)
        self.assertIn("created_at", session)
        self.assertIn("updated_at", session)
        self.assertGreater(len(session["created_at"]), 0)

    # --- Cascade delete ---

    def test_delete_session_deletes_messages(self):
        sid = self.db.create_session("test-model")
        self.db.add_message(sid, "user", "Hello")
        self.db.add_message(sid, "assistant", "Hi")
        self.db.delete_session(sid)
        # Session and messages should both be gone
        self.assertIsNone(self.db.get_session(sid))


class TestDatabaseErrors(unittest.TestCase):
    """Test error handling."""

    def test_invalid_path_raises(self):
        with self.assertRaises(DatabaseError):
            Database(db_path="/nonexistent/path/that/cannot/exist/db.sqlite")


if __name__ == "__main__":
    unittest.main()
