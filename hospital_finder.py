"""Lokale Zielklinik-Vorauswahl und niederlaendische Uebergabe.

Die Matrix ist eine pflegbare Planungsgrundlage. Sie bildet weder aktuelle
Aufnahmefaehigkeit noch verbindliche Transportstrategien ab.
"""

from math import asin, cos, radians, sin, sqrt
from urllib.parse import quote_plus


TOWNS = {
    "Ahaus": (52.075, 7.007), "Bocholt": (51.838, 6.615), "Borken": (51.844, 6.858),
    "Gescher": (51.954, 7.004), "Gronau": (52.212, 7.026), "Heek": (52.117, 7.103),
    "Heiden": (51.824, 6.935), "Isselburg": (51.832, 6.464), "Legden": (52.033, 7.100),
    "Raesfeld": (51.766, 6.840), "Reken": (51.832, 7.044), "Rhede": (51.835, 6.696),
    "Schöppingen": (52.094, 7.232), "Stadtlohn": (51.994, 6.920), "Südlohn": (51.944, 6.869),
    "Velen": (51.894, 6.989), "Vreden": (52.037, 6.829),
}

CATEGORIES = [
    "Allgemeine Notaufnahme", "Neurologie / Stroke", "Herzkatheter / ACS",
    "Reanimation / Cardiac Arrest", "Urologie", "Pädiatrie",
    "Gynäkologie / Geburtshilfe", "Unfallchirurgie / Trauma",
]

HOSPITALS = [
    {
        "id": "ahaus", "name": "St. Marien-Krankenhaus Ahaus", "country": "DE",
        "address": "Wüllener Straße 101, 48683 Ahaus", "coords": (52.0719, 7.0153),
        "categories": {"Allgemeine Notaufnahme", "Urologie", "Gynäkologie / Geburtshilfe", "Unfallchirurgie / Trauma"},
        "source": "https://www.klinikum-westmuensterland.de/st-marien-krankenhaus-ahaus/",
    },
    {
        "id": "bocholt", "name": "St. Agnes-Hospital Bocholt", "country": "DE",
        "address": "Barloer Weg 125, 46397 Bocholt", "coords": (51.8525, 6.6250),
        "categories": {"Allgemeine Notaufnahme", "Herzkatheter / ACS", "Reanimation / Cardiac Arrest", "Urologie", "Pädiatrie", "Gynäkologie / Geburtshilfe", "Unfallchirurgie / Trauma"},
        "source": "https://www.klinikum-westmuensterland.de/st-agnes-hospital-bocholt/",
    },
    {
        "id": "borken", "name": "St. Marien-Hospital Borken", "country": "DE",
        "address": "Am Boltenhof 7, 46325 Borken", "coords": (51.8507, 6.8652),
        "categories": {"Allgemeine Notaufnahme", "Neurologie / Stroke", "Unfallchirurgie / Trauma"},
        "source": "https://www.klinikum-westmuensterland.de/st-marien-hospital-borken/unsere-leistungen/fachabteilungen/neurologie/",
    },
    {
        "id": "winterswijk", "name": "Streekziekenhuis Koningin Beatrix (SKB)", "country": "NL",
        "address": "Beatrixpark 1, 7101 BN Winterswijk, Nederland", "coords": (51.9749, 6.7193),
        "categories": {"Allgemeine Notaufnahme", "Neurologie / Stroke", "Pädiatrie", "Unfallchirurgie / Trauma"},
        "source": "https://www.skbwinterswijk.nl/spoedeisende-hulp",
    },
    {
        "id": "enschede", "name": "Medisch Spectrum Twente (MST)", "country": "NL",
        "address": "Koningsplein 1, 7512 KZ Enschede, Nederland", "coords": (52.2172, 6.8937),
        "categories": set(CATEGORIES),
        "source": "https://www.mst.nl/afdelingen/spoedeisende-hulp",
    },
]


def distance_km(origin, destination):
    lat1, lon1 = map(radians, origin)
    lat2, lon2 = map(radians, destination)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(value))


def suitable_hospitals(town, category):
    origin = TOWNS[town]
    matches = []
    for hospital in HOSPITALS:
        if category not in hospital["categories"]:
            continue
        item = dict(hospital)
        item["distance_km"] = distance_km(origin, hospital["coords"])
        item["route_url"] = (
            "https://www.google.com/maps/dir/?api=1&origin=" + quote_plus(f"{town}, Kreis Borken")
            + "&destination=" + quote_plus(hospital["address"]) + "&travelmode=driving"
        )
        matches.append(item)
    return sorted(matches, key=lambda item: item["distance_km"])


def glucose_mmol(mg_dl):
    try:
        value = float(mg_dl)
    except (TypeError, ValueError):
        return None
    return round(value / 18.0182, 1) if value > 0 else None


def build_dutch_protocol(patient):
    v = patient.get("vitalwerte", {})
    x = patient.get("xabcde", {})
    s = patient.get("samplers", {})
    m = patient.get("massnahmen", {})
    target = patient.get("transport", {})

    lines = [
        "AMBULANCEVERSLAG – NEDERLANDSE OVERDRACHT",
        "=" * 52,
        "Gestructureerde overdracht; alle gegevens vóór gebruik controleren.",
        "Vrije tekstvelden worden ongewijzigd overgenomen.",
        "",
        "BESTEMMING",
        f"Ziekenhuis: {target.get('hospital_name', 'Niet vastgelegd')}",
        f"Vertrekplaats: {target.get('town', 'Niet vastgelegd')}",
        f"Doelcategorie: {target.get('category', 'Niet vastgelegd')}",
        "",
        "PATIËNT",
    ]
    if v.get("alter"):
        lines.append(f"Leeftijd: {v['alter']} jaar")
    if v.get("geschlecht"):
        gender = {"männlich": "man", "weiblich": "vrouw", "divers": "divers", "Unbekannt": "onbekend"}.get(v["geschlecht"], v["geschlecht"])
        lines.append(f"Geslacht: {gender}")
    if v.get("auffindesituation"):
        lines.append(f"Aantrefsituatie: {v['auffindesituation']}")
    if s.get("symptome"):
        lines.append(f"Klachten/symptomen: {s['symptome']}")
    if s.get("ereignis"):
        lines.append(f"Gebeurtenis: {s['ereignis']}")

    lines.extend(["", "VITALE PARAMETERS"])
    if v.get("rr_sys") and v.get("rr_dia"):
        lines.append(f"Bloeddruk: {v['rr_sys']}/{v['rr_dia']} mmHg")
    if v.get("puls"):
        lines.append(f"Polsfrequentie: {v['puls']}/min")
    if v.get("spo2"):
        lines.append(f"Zuurstofsaturatie: {v['spo2']} %")
    if v.get("af"):
        lines.append(f"Ademfrequentie: {v['af']}/min")
    if v.get("gcs"):
        lines.append(f"Glasgow Coma Scale: {v['gcs']}/15")
    if v.get("temperatur") is not None:
        lines.append(f"Temperatuur: {v['temperatur']} °C")
    mmol = glucose_mmol(v.get("bz"))
    if mmol is not None:
        mmol_text = f"{mmol:.1f}".replace(".", ",")
        lines.append(f"Bloedglucose: {mmol_text} mmol/L ({v['bz']} mg/dL)")

    lines.extend(["", "ABCDE"])
    mapping = [
        ("A Luchtweg", x.get("atemweg")), ("B Ademhaling", x.get("atmung")),
        ("C Huid/circulatie", x.get("haut")), ("D Bewustzijn (AVPU)", x.get("avpu")),
        ("E Lichamelijk onderzoek", x.get("bodycheck")),
    ]
    for label, value in mapping:
        if value and value != "Keine Angabe":
            lines.append(f"{label}: {value}")

    lines.extend(["", "ANAMNESE"])
    if s.get("allergien"):
        allergy = "geen bekend" if s.get("allergien") == "Keine bekannt" else s.get("allergien_text") or s.get("allergien")
        lines.append(f"Allergieën: {allergy}")
    if s.get("medikamente"):
        lines.append(f"Thuismedicatie: {s['medikamente']}")
    if s.get("vorgeschichte"):
        lines.append(f"Medische voorgeschiedenis: {s['vorgeschichte']}")

    timeline = m.get("timeline", [])
    medications = m.get("medikation", [])
    if timeline or medications:
        lines.extend(["", "BEHANDELING EN TIJDLIJN"])
    for entry in timeline:
        lines.append(f"{entry.get('zeit', '--:--')} – {entry.get('massnahme', '')}; effect: {entry.get('wirkung', 'niet vastgelegd')}")
    for med in medications:
        lines.append(f"{med.get('zeit', '--:--')} – {med.get('name', '')}, dosis {med.get('dosis', '')}, route {med.get('weg', '')}")
    lines.extend(["", "Opmerking: lokale afspraken, meldkamer en actuele opnamecapaciteit zijn leidend."])
    return "\n".join(lines)
