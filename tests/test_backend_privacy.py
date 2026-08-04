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

    def test_display_datetime_label_uses_german_pdf_format(self):
        label = main.display_datetime_label("2026-08-04T17:05:32+02:00")

        self.assertEqual(label, "04.08.2026 17:05 Uhr")

    def test_medication_calculator_exposes_ruleset_version(self):
        result = main.calculate_medication(main.MedicationCalcRequest())

        self.assertEqual(result["ruleset_version"], main.MEDICAL_RULESET_VERSION)

    def test_protocol_includes_team_partner_and_bodycheck_regions(self):
        protocol = main.generate_protocol_text({
            "besatzung": {
                "verantwortlicher": "Florian",
                "fahrer": "Max",
            },
            "xabcde": {
                "bodycheck": "Auffällig",
                "trauma_befunde": [
                    {
                        "region": "thorax_links",
                        "side": "vorne",
                        "verletzungsarten": ["Druckschmerz"],
                        "blutung": "gering",
                        "notiz": "Schürfwunde",
                    }
                ],
            },
        })

        self.assertIn("Teampartner/in: Max", protocol)
        self.assertIn("E Bodycheck: Auffällig", protocol)
        self.assertIn("vorne: Brustkorb links - Druckschmerz; Blutung: gering; Schürfwunde", protocol)

    def test_protocol_includes_joint_case_marker(self):
        protocol = main.generate_protocol_text({
            "gemeinsamer_einsatz": {
                "id": "nana abcd 1234",
                "role": "uebernehmen",
                "source_employee_name": "RTW 1",
                "vehicle": "KTW",
                "linked_at": "04.08.2026 18:00",
            }
        })

        self.assertIn("GEMEINSAMER EINSATZ", protocol)
        self.assertIn("Gemeinsame Einsatz-ID: NANA-ABCD-1234", protocol)
        self.assertIn("Rolle: Einsatz wurde übernommen", protocol)

    def test_protocol_includes_sorted_chronology_and_handover_summary(self):
        protocol = main.generate_protocol_text({
            "vitalwerte": {
                "alter": "45",
                "geschlecht": "männlich",
                "kurzbericht": "Thoraxschmerz seit dem Morgen",
                "rr_sys": "160",
                "rr_dia": "95",
                "puls": "112",
                "spo2": "94",
                "af": "22",
                "gcs": "15",
            },
            "xabcde": {"atemweg": "frei", "atmung": "tachypnoe", "haut": "blass", "avpu": "Alert", "bodycheck": "Unauffällig"},
            "samplers": {"symptome": "Thoraxdruck", "ereignis": "Belastungsbeginn"},
            "opqrst": {"schmerz_vorhanden": "Ja", "onset": "08:05", "quality": "Drückend", "region": "Thorax", "nrs": "8"},
            "amls": {"arbeitsdiagnose": "ACS-Verdacht"},
            "massnahmen": {
                "timeline": [
                    {"zeit": "08:15", "massnahme": "Monitoring angelegt"},
                    {"zeit": "08:10", "massnahme": "12-Kanal-EKG geschrieben"},
                ],
                "medikation": [{"zeit": "08:20", "medikament": "ASS", "dosis": "250 mg", "weg": "i.v."}],
            },
            "uebergabe": {"ziel": "Chest-Pain-Unit", "text": "Voranmeldung erfolgt", "lagerung": "Oberkörper hoch"},
        })

        self.assertIn("EINSATZCHRONOLOGIE", protocol)
        chronology = protocol.split("EINSATZCHRONOLOGIE", 1)[1]
        self.assertLess(chronology.index("08:05 - Schmerzassessment"), chronology.index("08:10 - 12-Kanal-EKG geschrieben"))
        self.assertLess(chronology.index("08:10 - 12-Kanal-EKG geschrieben"), chronology.index("08:15 - Monitoring angelegt"))
        self.assertLess(chronology.index("08:15 - Monitoring angelegt"), chronology.index("08:20 - Medikation: ASS, 250 mg, i.v."))
        self.assertIn("ÜBERGABE-KURZFAZIT", protocol)
        self.assertIn("Die Versorgung wurde auf Übergabe an Chest-Pain-Unit ausgerichtet.", protocol)

    def test_quality_flags_context_sensitive_gaps(self):
        quality = main.assess_protocol_quality({
            "patient": {"patientengruppe": "Erwachsener"},
            "vitalwerte": {"alter": "45", "puls": "145", "spo2": "88", "rr_sys": "210", "rr_dia": "110", "af": "34", "gcs": "15"},
            "xabcde": {
                "atemweg": "frei",
                "atmung": "Dyspnoe",
                "haut": "blass",
                "avpu": "Alert",
                "bodycheck": "Auffällig",
                "befast_face": "Fazialisparese links",
            },
            "opqrst": {"schmerz_vorhanden": "Ja", "nrs": "8"},
            "amls": {"arbeitsdiagnose": "Schmerz-/Stressreaktion"},
            "uebergabe": {},
            "massnahmen": {"timeline": [], "medikation": []},
            "reanimation": {"active": False},
        })

        by_id = {item["id"]: item for item in quality["items"]}
        self.assertEqual(by_id["bodycheck_detail"]["status"], "warning")
        self.assertEqual(by_id["befast_time"]["status"], "warning")
        self.assertEqual(by_id["pain_reassessment"]["status"], "warning")
        self.assertEqual(by_id["abnormal_vitals_context"]["status"], "warning")

        reanimation_quality = main.assess_protocol_quality({
            "patient": {"patientengruppe": "Erwachsener"},
            "vitalwerte": {"alter": "45", "puls": "80", "spo2": "98", "rr_sys": "120", "rr_dia": "80", "af": "16", "gcs": "15"},
            "xabcde": {"atemweg": "frei", "atmung": "unauffällig", "haut": "rosig", "avpu": "Alert"},
            "opqrst": {"schmerz_vorhanden": "Nein"},
            "amls": {"arbeitsdiagnose": "Reanimation"},
            "uebergabe": {"ziel": "Klinik", "text": "Übergabe erfolgt"},
            "reanimation": {"active": True, "rosc": "Ja"},
        })
        by_id = {item["id"]: item for item in reanimation_quality["items"]}
        self.assertEqual(by_id["reanimation_core"]["status"], "critical")
        self.assertGreaterEqual(quality["critical_count"], 1)


if __name__ == "__main__":
    unittest.main()
