import base64
import json
from datetime import datetime


def _clean(value):
    if value in [None, "", [], {}, "Keine Angabe"]:
        return None
    return value


def _compact_dict(values):
    return {key: value for key, value in values.items() if _clean(value) is not None}


def build_nana_case_export(patient, protocol_text="", metadata=None):
    metadata = metadata or {}
    return {
        "resourceType": "NANAEmergencyCase",
        "schemaVersion": "0.1",
        "exportedAt": datetime.now().isoformat(timespec="seconds"),
        "privacy": {
            "mode": "local_export",
            "externalTransmission": False,
            "note": "Diese Datei wird lokal erzeugt. Weitergabe nur an berechtigte Stellen.",
        },
        "metadata": _compact_dict(metadata),
        "dispatch": _compact_dict(patient.get("einsatz", {})),
        "patient": {
            "vitalwerte": patient.get("vitalwerte", {}),
            "xabcde": patient.get("xabcde", {}),
            "samplers": patient.get("samplers", {}),
            "opqrst": patient.get("opqrst", {}),
            "einweisung": patient.get("einweisung", {}),
            "amls": patient.get("amls", {}),
            "massnahmen": patient.get("massnahmen", {}),
            "transport": patient.get("transport", {}),
        },
        "protocolText": protocol_text or "",
    }


def build_fhir_bundle(patient, protocol_text="", metadata=None):
    metadata = metadata or {}
    case = build_nana_case_export(patient, protocol_text, metadata)
    vital = patient.get("vitalwerte", {})
    einsatz = patient.get("einsatz", {})
    transport = patient.get("transport", {})

    bundle_id = metadata.get("case_id") or einsatz.get("einsatznummer") or "nana-current-case"
    patient_ref = "Patient/nana-patient"
    encounter_ref = "Encounter/nana-encounter"

    observations = []
    observation_specs = [
        ("puls", "8867-4", "Heart rate", "/min"),
        ("spo2", "59408-5", "Oxygen saturation in Arterial blood by Pulse oximetry", "%"),
        ("af", "9279-1", "Respiratory rate", "/min"),
        ("rr_sys", "8480-6", "Systolic blood pressure", "mm[Hg]"),
        ("rr_dia", "8462-4", "Diastolic blood pressure", "mm[Hg]"),
        ("temperatur", "8310-5", "Body temperature", "Cel"),
        ("bz", "2339-0", "Glucose", "mg/dL"),
    ]
    for key, code, display, unit in observation_specs:
        value = _clean(vital.get(key))
        if value is None:
            continue
        try:
            numeric_value = float(str(value).replace(",", "."))
        except ValueError:
            numeric_value = None
        resource = {
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [{"system": "http://loinc.org", "code": code, "display": display}],
                "text": display,
            },
            "subject": {"reference": patient_ref},
            "encounter": {"reference": encounter_ref},
        }
        if numeric_value is not None:
            resource["valueQuantity"] = {"value": numeric_value, "unit": unit}
        else:
            resource["valueString"] = str(value)
        observations.append(resource)

    diagnostic_text = patient.get("amls", {}).get("arbeitsdiagnose") or patient.get("einweisung", {}).get("diagnose")

    entries = [
        {
            "fullUrl": f"urn:uuid:{bundle_id}-patient",
            "resource": {
                "resourceType": "Patient",
                "id": "nana-patient",
                "extension": [
                    {
                        "url": "https://nana.local/fhir/StructureDefinition/privacy-note",
                        "valueString": "FHIR-Startpunkt ohne automatische externe Uebertragung.",
                    }
                ],
            },
        },
        {
            "fullUrl": f"urn:uuid:{bundle_id}-encounter",
            "resource": {
                "resourceType": "Encounter",
                "id": "nana-encounter",
                "status": "finished" if protocol_text else "in-progress",
                "class": {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                    "code": "EMER",
                    "display": "emergency",
                },
                "subject": {"reference": patient_ref},
                "identifier": [
                    item for item in [
                        {"system": "https://nana.local/dispatch/case-number", "value": einsatz.get("einsatznummer")}
                        if einsatz.get("einsatznummer") else None,
                        {"system": "https://nana.local/dispatch/vehicle", "value": einsatz.get("fahrzeug")}
                        if einsatz.get("fahrzeug") else None,
                    ]
                    if item
                ],
                "reasonCode": [{"text": einsatz.get("stichwort")}] if einsatz.get("stichwort") else [],
            },
        },
    ]

    if diagnostic_text:
        entries.append({
            "fullUrl": f"urn:uuid:{bundle_id}-condition",
            "resource": {
                "resourceType": "Condition",
                "clinicalStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                    }]
                },
                "subject": {"reference": patient_ref},
                "encounter": {"reference": encounter_ref},
                "code": {"text": diagnostic_text},
            },
        })

    for index, observation in enumerate(observations, start=1):
        entries.append({"fullUrl": f"urn:uuid:{bundle_id}-observation-{index}", "resource": observation})

    if transport.get("hospital_name") or protocol_text:
        entries.append({
            "fullUrl": f"urn:uuid:{bundle_id}-document",
            "resource": {
                "resourceType": "DocumentReference",
                "status": "current",
                "subject": {"reference": patient_ref},
                "context": {"encounter": [{"reference": encounter_ref}]},
                "description": transport.get("hospital_name") or "NANA Einsatzprotokoll",
                "content": [{
                    "attachment": {
                        "contentType": "text/plain",
                        "title": "NANA Einsatzprotokoll",
                        "data": base64.b64encode(protocol_text.encode("utf-8")).decode("ascii"),
                    }
                }],
            },
        })

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "id": str(bundle_id),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "meta": {
            "tag": [{
                "system": "https://nana.local/security",
                "code": "local-export-only",
                "display": "Local export only",
            }]
        },
        "entry": entries,
        "containedNanaCase": case,
    }


def parse_dispatch_import(raw_text):
    data = json.loads(raw_text)
    if not isinstance(data, dict):
        raise ValueError("Die Importdatei muss ein JSON-Objekt enthalten.")

    source = data.get("dispatch") if isinstance(data.get("dispatch"), dict) else data
    aliases = {
        "einsatznummer": ["einsatznummer", "caseNumber", "incidentNumber", "nummer"],
        "stichwort": ["stichwort", "keyword", "alarmKeyword", "meldebild"],
        "alarmzeit": ["alarmzeit", "alarmTime", "dispatchedAt"],
        "adresse": ["adresse", "address", "streetAddress", "einsatzort"],
        "ort": ["ort", "town", "city"],
        "koordinaten": ["koordinaten", "coordinates", "geo"],
        "fahrzeug": ["fahrzeug", "vehicle", "unit"],
        "leitstelle": ["leitstelle", "dispatchCenter", "controlCenter"],
        "bemerkung": ["bemerkung", "note", "remarks"],
    }

    imported = {}
    for target, keys in aliases.items():
        for key in keys:
            value = source.get(key)
            if _clean(value) is not None:
                imported[target] = value
                break

    return imported
