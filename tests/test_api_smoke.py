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

        warning_finish = self.client.post("/api/cases/finish", headers={"X-NANA-CSRF": csrf}, json={
            "patient": {
                "patient": {"patientengruppe": "Erwachsener", "alter_wert": "45"},
                "vitalwerte": {"bewusstsein": "wach"},
                "einsatz": {"einsatznummer": "TEST-1"},
            },
            "force_finish": False,
        })
        self.assertEqual(warning_finish.status_code, 409)
        self.assertIn("quality", warning_finish.json()["detail"])

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

        readiness = self.client.get("/api/admin/production-readiness")
        self.assertEqual(readiness.status_code, 200)
        readiness_payload = readiness.json()
        self.assertIn(readiness_payload["overall"], {"ok", "warning", "critical"})
        self.assertIn("counts", readiness_payload)
        self.assertGreaterEqual(len(readiness_payload["items"]), 8)
        self.assertTrue(any(item["id"] == "data_key" for item in readiness_payload["items"]))

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

    def test_joint_chat_invite_decline_and_ciphertext_message_flow(self):
        setup = self.client.post("/api/auth/setup-first-admin", json={
            "name": "Admin",
            "password": "Sehr-sicheres-passwort-2026!",
            "device_id": "sender-device",
        })
        self.assertEqual(setup.status_code, 200)
        sender_csrf = self.client.cookies.get("nana_csrf")

        storage.create_employee_record({
            "id": "target-employee",
            "name": "Gescher KTW 3",
            "role": "employee",
            "qualification": "Rettungssanitäter",
            "station": "Gescher",
            "vehicle_scope": "KTW",
            "on_shift": True,
            "active": True,
            "password_hash": main.password_hash("Sehr-sicheres-passwort-2026!"),
            "must_change_password": False,
        })
        target_client = TestClient(main.app)
        self.addCleanup(target_client.close)
        target_login = target_client.post("/api/auth/login", json={
            "employee_id": "target-employee",
            "password": "Sehr-sicheres-passwort-2026!",
            "device_id": "target-device",
        })
        self.assertEqual(target_login.status_code, 200)
        target_csrf = target_client.cookies.get("nana_csrf")

        sender_device = self.client.put("/api/joint-cases/chat/device", headers={"X-NANA-CSRF": sender_csrf}, json={
            "device_id": "sender-device",
            "device_name": "Sender Tablet",
            "public_key": '{"kty":"EC","crv":"P-256","x":"sender","y":"sender"}',
        })
        self.assertEqual(sender_device.status_code, 200)
        target_device = target_client.put("/api/joint-cases/chat/device", headers={"X-NANA-CSRF": target_csrf}, json={
            "device_id": "target-device",
            "device_name": "Target Tablet",
            "public_key": '{"kty":"EC","crv":"P-256","x":"target","y":"target"}',
        })
        self.assertEqual(target_device.status_code, 200)

        invite = self.client.post("/api/joint-cases/chat/invites", headers={"X-NANA-CSRF": sender_csrf}, json={
            "target_device_id": "target-device",
            "sender_device_id": "sender-device",
            "sender_public_key": '{"kty":"EC","crv":"P-256","x":"sender","y":"sender"}',
            "encrypted_room_key": "cipher-room-key",
            "room_key_iv": "cipher-iv",
            "joint_case_id": "NANA-ABCD-1234",
        })
        self.assertEqual(invite.status_code, 200)
        invite_payload = invite.json()["invite"]
        self.assertEqual(invite_payload["status"], "pending")

        declined = target_client.post("/api/joint-cases/chat/invites/decision", headers={"X-NANA-CSRF": target_csrf}, json={
            "invite_id": invite_payload["id"],
            "status": "declined",
        })
        self.assertEqual(declined.status_code, 200)
        self.assertEqual(declined.json()["invite"]["status"], "declined")

        state = self.client.get("/api/joint-cases/chat/state?device_id=sender-device")
        self.assertEqual(state.status_code, 200)
        self.assertTrue(any(item["status"] == "declined" for item in state.json()["invites"]))

        accepted_invite = self.client.post("/api/joint-cases/chat/invites", headers={"X-NANA-CSRF": sender_csrf}, json={
            "target_device_id": "target-device",
            "sender_device_id": "sender-device",
            "sender_public_key": '{"kty":"EC","crv":"P-256","x":"sender","y":"sender"}',
            "encrypted_room_key": "cipher-room-key-2",
            "room_key_iv": "cipher-iv-2",
            "joint_case_id": "NANA-ABCD-1234",
        })
        self.assertEqual(accepted_invite.status_code, 200)
        accepted_payload = accepted_invite.json()["invite"]
        accepted = target_client.post("/api/joint-cases/chat/invites/decision", headers={"X-NANA-CSRF": target_csrf}, json={
            "invite_id": accepted_payload["id"],
            "status": "accepted",
        })
        self.assertEqual(accepted.status_code, 200)
        thread_id = accepted.json()["thread"]["id"]

        sent = self.client.post("/api/joint-cases/chat/messages", headers={"X-NANA-CSRF": sender_csrf}, json={
            "thread_id": thread_id,
            "sender_device_id": "sender-device",
            "ciphertext": "encrypted-only",
            "iv": "message-iv",
        })
        self.assertEqual(sent.status_code, 200)
        messages = target_client.get(f"/api/joint-cases/chat/threads/{thread_id}/messages")
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(messages.json()["messages"][0]["ciphertext"], "encrypted-only")
        self.assertNotIn("text", messages.json()["messages"][0])


if __name__ == "__main__":
    unittest.main()
