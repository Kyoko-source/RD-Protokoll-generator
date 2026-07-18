import os
import tempfile
import unittest

import storage
from backend import main
from fastapi.testclient import TestClient


class ApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_db_path = storage.DB_PATH
        self.previous_data_key = os.environ.get("NANA_DATA_KEY")
        os.environ["NANA_DATA_KEY"] = "api-test-data-key"
        storage.DB_PATH = os.path.join(self.tmp.name, "nana-api-test.db")
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        storage.DB_PATH = self.previous_db_path
        if self.previous_data_key is None:
            os.environ.pop("NANA_DATA_KEY", None)
        else:
            os.environ["NANA_DATA_KEY"] = self.previous_data_key
        self.tmp.cleanup()

    def test_health_reports_database_and_ruleset_status(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["app"], "NANA")
        self.assertTrue(payload["database"]["ok"])
        self.assertEqual(payload["ruleset_version"], main.MEDICAL_RULESET_VERSION)
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("object-src 'none'", response.headers["content-security-policy"])
        self.assertIn("default-src 'self'", response.headers["content-security-policy"])
        self.assertIn("security", payload)

    def test_first_admin_login_me_and_case_finish(self):
        setup = self.client.post("/api/auth/setup-first-admin", json={
            "name": "Admin",
            "password": "Sehr-sicheres-passwort-2026!",
            "device_id": "device-1",
            "user_agent": "Mozilla/5.0 Windows Chrome/120",
        })

        self.assertEqual(setup.status_code, 200)
        setup_payload = setup.json()
        self.assertNotIn("token", setup_payload)
        self.assertIn("nana_session", setup.cookies)
        self.assertIn("nana_csrf", setup.cookies)
        self.assertIn("HttpOnly", setup.headers.get("set-cookie", ""))

        login = self.client.post("/api/auth/login", json={
            "employee_id": setup_payload["employee"]["id"],
            "password": "Sehr-sicheres-passwort-2026!",
        })
        self.assertEqual(login.status_code, 200)
        self.assertNotIn("token", login.json())

        me = self.client.get("/api/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["employee"]["role"], "admin")

        csrf = self.client.cookies.get("nana_csrf")
        blocked_finish = self.client.post("/api/cases/finish", json={
            "patient": {"patient": {"patientengruppe": "Erwachsener"}},
            "force_finish": True,
        })
        self.assertEqual(blocked_finish.status_code, 403)

        finish = self.client.post("/api/cases/finish", headers={"X-NANA-CSRF": csrf}, json={
            "patient": {
                "patient": {"patientengruppe": "Erwachsener", "alter_wert": "45"},
                "vitalwerte": {"bewusstsein": "wach"},
                "einsatz": {"einsatznummer": "TEST-1"},
            },
            "force_finish": True,
        })
        self.assertEqual(finish.status_code, 200)
        self.assertEqual(finish.json()["ruleset_version"], main.MEDICAL_RULESET_VERSION)

    def test_weak_first_admin_password_is_rejected(self):
        response = self.client.post("/api/auth/setup-first-admin", json={
            "name": "Admin",
            "password": "zu-kurz",
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("Passwort muss enthalten", response.json()["detail"])

    def test_large_request_body_is_rejected(self):
        response = self.client.post(
            "/api/auth/setup-first-admin",
            content="x" * (main.MAX_REQUEST_BODY_BYTES + 1),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
