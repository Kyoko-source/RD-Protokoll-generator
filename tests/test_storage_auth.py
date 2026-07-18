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

    def test_security_events_keep_encrypted_metadata_and_roundtrip(self):
        storage.write_audit_event({
            "timestamp": "2026-07-18T10:00:00",
            "employee_id": "employee-1",
            "employee_name": "Admin",
            "action": "api_login_success",
            "entity_type": "session",
            "entity_id": "session-1",
            "details": {"role": "admin"},
        })
        storage.write_login_event({
            "timestamp": "2026-07-18T10:01:00",
            "employee_id": "employee-1",
            "employee_name": "Admin",
            "device_id": "device-hash",
            "device_name": "Tablet 1",
            "user_agent": "Chrome / Windows",
            "ip_address": "192.168.1.0",
            "source": "login",
        })

        self.assertEqual(storage.list_audit_events()[0]["employee_name"], "Admin")
        self.assertEqual(storage.list_audit_events()[0]["details"]["role"], "admin")
        self.assertEqual(storage.list_login_events()[0]["device_name"], "Tablet 1")

        with storage._connect() as connection:
            audit = connection.execute("SELECT * FROM audit_log").fetchone()
            login = connection.execute("SELECT * FROM login_events").fetchone()

        for column in ("timestamp", "employee_id", "employee_name", "action", "entity_type", "entity_id", "details_json"):
            self.assertTrue(audit[column].startswith(storage.ENCRYPTED_PREFIX), column)
        for column in ("timestamp", "employee_id", "employee_name", "device_id", "device_name", "user_agent", "ip_address", "source"):
            self.assertTrue(login[column].startswith(storage.ENCRYPTED_PREFIX), column)

    def test_existing_security_events_are_encrypted_and_purgeable(self):
        storage.init_database()
        with storage._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_log (
                    timestamp, employee_id, employee_name, action,
                    entity_type, entity_id, details_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("2026-07-01T10:00:00", "employee-1", "Admin", "api_login_success", "session", "session-1", "{}"),
            )
            connection.execute(
                """
                INSERT INTO login_events (
                    timestamp, employee_id, employee_name, device_id,
                    device_name, user_agent, ip_address, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("2026-07-20T10:00:00", "employee-1", "Admin", "device-hash", "Tablet 1", "Chrome / Windows", "192.168.1.0", "login"),
            )
            connection.commit()

        changed = storage.encrypt_existing_patient_data()
        self.assertEqual(changed, 2)

        with storage._connect() as connection:
            audit = connection.execute("SELECT timestamp, employee_name FROM audit_log").fetchone()
            login = connection.execute("SELECT timestamp, device_name FROM login_events").fetchone()

        self.assertTrue(audit["timestamp"].startswith(storage.ENCRYPTED_PREFIX))
        self.assertTrue(audit["employee_name"].startswith(storage.ENCRYPTED_PREFIX))
        self.assertTrue(login["timestamp"].startswith(storage.ENCRYPTED_PREFIX))
        self.assertTrue(login["device_name"].startswith(storage.ENCRYPTED_PREFIX))

        deleted = storage.delete_security_events_before("2026-07-10T00:00:00")

        self.assertEqual(deleted, {"audit_log": 1, "login_events": 0})
        self.assertEqual(storage.list_login_events()[0]["employee_name"], "Admin")


if __name__ == "__main__":
    unittest.main()
