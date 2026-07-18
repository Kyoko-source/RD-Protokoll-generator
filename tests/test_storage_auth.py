import os
import tempfile
import unittest
from datetime import datetime, timedelta

import storage


class StorageAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_db_path = storage.DB_PATH
        self.previous_data_key = os.environ.get("NANA_DATA_KEY")
        os.environ["NANA_DATA_KEY"] = "test-data-key"
        storage.DB_PATH = os.path.join(self.tmp.name, "nana-test.db")

    def tearDown(self):
        storage.DB_PATH = self.previous_db_path
        if self.previous_data_key is None:
            os.environ.pop("NANA_DATA_KEY", None)
        else:
            os.environ["NANA_DATA_KEY"] = self.previous_data_key
        self.tmp.cleanup()

    def test_init_database_creates_auth_tables_and_ruleset_column(self):
        storage.init_database()
        with storage._connect() as connection:
            tables = {
                row["name"]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
            }
            finished_case_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(finished_cases)").fetchall()
            }

        self.assertIn("schema_migrations", tables)
        self.assertIn("auth_sessions", tables)
        self.assertIn("password_change_tokens", tables)
        self.assertIn("auth_failures", tables)
        self.assertIn("ruleset_version", finished_case_columns)

    def test_session_and_password_change_token_roundtrip(self):
        expires_at = datetime.now() + timedelta(minutes=30)
        storage.save_auth_session("session-token", "employee-1", expires_at)
        storage.save_password_change_token("change-token", "employee-1", expires_at)

        self.assertEqual(storage.get_auth_session("session-token")["employee_id"], "employee-1")
        self.assertEqual(storage.get_password_change_token("change-token")["employee_id"], "employee-1")

        storage.delete_auth_session("session-token")
        storage.delete_password_change_token("change-token")

        self.assertIsNone(storage.get_auth_session("session-token"))
        self.assertIsNone(storage.get_password_change_token("change-token"))

    def test_finished_case_keeps_encrypted_payload_and_ruleset_version(self):
        storage.save_finished_case({
            "id": "case-1",
            "employee_id": "employee-1",
            "employee_name": "Test",
            "completed_at": "2026-07-18T10:00:00",
            "summary": "Testfall",
            "patient": {"patient": {"name": "Max"}},
            "protocol_text": "Patient Max dokumentiert.",
            "retention_until": "2026-08-18",
            "ruleset_version": "NANA-SOP-test",
        })

        loaded = storage.get_finished_case("case-1")
        self.assertEqual(loaded["patient"]["patient"]["name"], "Max")
        self.assertEqual(loaded["protocol_text"], "Patient Max dokumentiert.")
        self.assertEqual(loaded["ruleset_version"], "NANA-SOP-test")

        with storage._connect() as connection:
            row = connection.execute(
                "SELECT summary, patient_json, protocol_text FROM finished_cases WHERE id = ?",
                ("case-1",),
            ).fetchone()

        self.assertTrue(row["summary"].startswith(storage.ENCRYPTED_PREFIX))
        self.assertTrue(row["patient_json"].startswith(storage.ENCRYPTED_PREFIX))
        self.assertTrue(row["protocol_text"].startswith(storage.ENCRYPTED_PREFIX))


if __name__ == "__main__":
    unittest.main()
