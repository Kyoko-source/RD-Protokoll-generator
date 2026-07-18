import unittest
from datetime import datetime

from backend import main


class BackendPrivacyTests(unittest.TestCase):
    def test_audit_details_redact_patient_like_fields(self):
        redacted = main.redact_audit_details({
            "summary": "Name, Adresse, Diagnose",
            "format": "pdf",
            "source": "draft",
        })

        self.assertNotIn("summary", redacted)
        self.assertEqual(redacted["format"], "pdf")
        self.assertEqual(redacted["source"], "draft")

    def test_device_identifier_is_hashed(self):
        first = main.hashed_identifier("device-abc")
        second = main.hashed_identifier("device-abc")

        self.assertEqual(first, second)
        self.assertNotEqual(first, "device-abc")
        self.assertEqual(len(first), 20)

    def test_audit_details_convert_datetime_values(self):
        value = datetime(2026, 7, 18, 12, 30)
        redacted = main.redact_audit_details({"locked_until": value})

        self.assertEqual(redacted["locked_until"], "2026-07-18T12:30:00")

    def test_medication_calculator_exposes_ruleset_version(self):
        result = main.calculate_medication(main.MedicationCalcRequest())

        self.assertEqual(result["ruleset_version"], main.MEDICAL_RULESET_VERSION)


if __name__ == "__main__":
    unittest.main()
