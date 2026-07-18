import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRightLeft,
  Building2,
  Brain,
  Calculator,
  Cable,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Download,
  ExternalLink,
  FileText,
  HeartPulse,
  Home,
  Lock,
  LogOut,
  MapPinned,
  Megaphone,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Pill,
  Printer,
  RotateCcw,
  Save,
  Search,
  ShieldCheck,
  Stethoscope,
  Trash2,
  UserRound,
  UserPlus,
  Wrench
} from 'lucide-react';
import './styles.css';

function resolveApiBase() {
  const configured = import.meta.env.VITE_API_BASE;
  if (configured !== undefined) return configured;
  if (import.meta.env.PROD) return '';
  if (window.location.port === '8000') return '';
  const host = window.location.hostname || '127.0.0.1';
  return `${window.location.protocol}//${host}:8000`;
}

const API_BASE = resolveApiBase();
const SESSION_TIMEOUT_MS = 20 * 60 * 1000;
const EMPLOYEE_ROLE_OPTIONS = [
  { value: 'employee', label: 'Mitarbeiter' },
  { value: 'bufdi', label: 'BuFDi' },
  { value: 'azubi', label: 'Azubi' },
  { value: 'praktikant', label: 'Praktikant/in' },
  { value: 'admin', label: 'Admin' }
];
const EMPLOYEE_QUALIFICATION_OPTIONS = [
  { value: '', label: 'Keine Angabe' },
  { value: 'Rettungshelfer', label: 'Rettungshelfer' },
  { value: 'Rettungssanitäter', label: 'Rettungssanitäter' },
  { value: 'Rettungsassistent', label: 'Rettungsassistent' },
  { value: 'Notfallsanitäter', label: 'Notfallsanitäter' },
  { value: 'Notarzt', label: 'Notarzt' }
];
const EMPLOYEE_STATION_OPTIONS = [
  { value: '', label: 'Keine Wache' },
  { value: 'Gescher', label: 'Gescher' },
  { value: 'Südlohn', label: 'Südlohn' },
  { value: 'Isselburg', label: 'Isselburg' },
  { value: 'Schöppingen', label: 'Schöppingen' },
  { value: 'Bocholt', label: 'Bocholt' }
];
const EMPLOYEE_VEHICLE_OPTIONS = [
  { value: '', label: 'Keine Angabe' },
  { value: 'KTW', label: 'KTW' },
  { value: 'RTW', label: 'RTW' },
  { value: 'KTW/RTW', label: 'KTW & RTW' }
];
const FEEDBACK_STATUS_OPTIONS = ['offen', 'in Arbeit', 'beantwortet', 'erledigt', 'abgelehnt'];
const FEEDBACK_STATUS_LABELS = {
  offen: 'Offen',
  'in Arbeit': 'In Arbeit',
  beantwortet: 'Beantwortet',
  erledigt: 'Erledigt',
  abgelehnt: 'Abgelehnt'
};

function roleLabel(role) {
  return EMPLOYEE_ROLE_OPTIONS.find((item) => item.value === role)?.label || 'Mitarbeiter';
}

function qualificationLabel(qualification) {
  return EMPLOYEE_QUALIFICATION_OPTIONS.find((item) => item.value === qualification)?.label || 'Keine Angabe';
}

function stationLabel(station) {
  return EMPLOYEE_STATION_OPTIONS.find((item) => item.value === station)?.label || 'Keine Wache';
}

function vehicleScopeLabel(vehicleScope) {
  return EMPLOYEE_VEHICLE_OPTIONS.find((item) => item.value === vehicleScope)?.label || 'Keine Angabe';
}

function feedbackStatusLabel(status) {
  return FEEDBACK_STATUS_LABELS[status] || status || 'Offen';
}

function feedbackStatusClass(status) {
  return `feedback-status status-${String(status || 'offen').toLowerCase().replace(/\s+/g, '-')}`;
}

function announcementSignature(items) {
  const first = Array.isArray(items) ? items[0] : null;
  if (!first) return '';
  return first.id || `${first.title || ''}-${first.published_at || ''}`;
}

function localDraftKey(employeeId) {
  return `nana_local_draft_${employeeId || 'unknown'}`;
}

function clearLegacyLocalPatientDrafts() {
  try {
    Object.keys(localStorage)
      .filter((key) => key.startsWith('nana_local_draft_'))
      .forEach((key) => localStorage.removeItem(key));
  } catch {
    // Browser storage is intentionally not used for patient data.
  }
}

function loadLocalDraft(employeeId) {
  clearLegacyLocalPatientDrafts();
  return null;
}

function saveLocalDraft(employeeId, patient) {
  if (!employeeId || !patient) return null;
  clearLegacyLocalPatientDrafts();
  return null;
}

function clearLocalDraft(employeeId) {
  if (employeeId) {
    localStorage.removeItem(localDraftKey(employeeId));
  }
  clearLegacyLocalPatientDrafts();
}

function localShiftCrewKey(employeeId) {
  return `nana_shift_crew_${employeeId || 'unknown'}`;
}

function loadLocalShiftCrew(employeeId) {
  try {
    const raw = localStorage.getItem(localShiftCrewKey(employeeId));
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveLocalShiftCrew(employeeId, crew) {
  if (!employeeId || !crew) return;
  localStorage.setItem(localShiftCrewKey(employeeId), JSON.stringify({
    verantwortlicher: crew.verantwortlicher || '',
    verantwortlicher_id: crew.verantwortlicher_id || '',
    fahrer: crew.fahrer || '',
    fahrer_id: crew.fahrer_id || '',
    azubi: crew.azubi || '',
    azubi_id: crew.azubi_id || '',
    praktikant: crew.praktikant || '',
    praktikant_id: crew.praktikant_id || '',
    updatedAt: new Date().toISOString()
  }));
}

function browserDeviceId() {
  const key = 'nana_browser_device_id';
  let value = localStorage.getItem(key);
  if (!value) {
    value = `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    localStorage.setItem(key, value);
  }
  return value;
}

function browserDeviceInfo() {
  const platform = navigator.userAgentData?.platform || navigator.platform || 'unbekanntes System';
  const touch = navigator.maxTouchPoints > 0 ? 'Touch' : 'Desktop';
  return {
    device_id: browserDeviceId(),
    device_name: `${platform} · ${touch} · ${window.screen?.width || '?'}x${window.screen?.height || '?'}`,
    user_agent: navigator.userAgent || ''
  };
}

function hasValue(value) {
  return ![undefined, null, '', 'Keine Angabe', 'Selber eintragen'].includes(value) && !(Array.isArray(value) && value.length === 0);
}

const CUSTOM_STATUS = 'Selber eintragen';

const vitalStatusOptions = {
  spo2_status: ['Keine Angabe', 'Normal', 'Leicht erniedrigt', 'Kritisch erniedrigt', 'Nicht messbar', CUSTOM_STATUS],
  af_status: ['Keine Angabe', 'Bradypnoe', 'Normal', 'Tachypnoe', 'Schwere Tachypnoe', 'Apnoe', CUSTOM_STATUS],
  rr_status: ['Keine Angabe', 'Hypotonie', 'Normal', 'Leicht erhöht', 'Hypertonie', 'Hypertensive Krise', 'Nicht messbar', CUSTOM_STATUS],
  puls_status: ['Keine Angabe', 'Bradykardie', 'Normal', 'Tachykardie', 'Starke Tachykardie', 'Nicht tastbar', CUSTOM_STATUS],
  gcs_status: ['Keine Angabe', 'Normal', 'Leicht eingeschränkt', 'Mittelgradig eingeschränkt', 'Schwer eingeschränkt', CUSTOM_STATUS],
  bz_status: ['Keine Angabe', 'Hypoglykämie', 'Normal', 'Hyperglykämie', 'Nicht messbar', CUSTOM_STATUS],
  temperatur_status: ['Keine Angabe', 'Unterkühlung', 'Normal', 'Erhöht / subfebril', 'Fieber', 'Hohes Fieber', 'Nicht gemessen', CUSTOM_STATUS]
};

const samplersSections = [
  { key: 'S1', label: 'S1', title: 'Symptome' },
  { key: 'A', label: 'A', title: 'Allergien' },
  { key: 'M', label: 'M', title: 'Medikamente' },
  { key: 'P', label: 'P', title: 'Patientenvorgeschichte' },
  { key: 'L', label: 'L', title: 'Letzte Ereignisse' },
  { key: 'E', label: 'E', title: 'Ereignis' },
  { key: 'R', label: 'R', title: 'Risikofaktoren' },
  { key: 'S2', label: 'S2', title: 'Schwangerschaft' }
];

const xabcdeSections = [
  { key: 'X', label: 'X', title: 'Kritische Blutung' },
  { key: 'A', label: 'A', title: 'Airway' },
  { key: 'B', label: 'B', title: 'Breathing' },
  { key: 'C', label: 'C', title: 'Circulation' },
  { key: 'D', label: 'D', title: 'Disability' },
  { key: 'E', label: 'E', title: 'Exposure' }
];

const opqrstSections = [
  { key: 'O', label: 'O', title: 'Onset' },
  { key: 'P', label: 'P', title: 'Provocation/Palliation' },
  { key: 'Q', label: 'Q', title: 'Quality' },
  { key: 'R', label: 'R', title: 'Region/Radiation' },
  { key: 'S', label: 'S', title: 'Severity' },
  { key: 'T', label: 'T', title: 'Time' }
];

const handoverQuickOptions = {
  lagerung: ['Rückenlage', 'Oberkörper hoch', 'Schocklage', 'Seitenlage', 'Sitzend', 'Tragestuhl', 'Schaufeltrage', 'Vakuummatratze'],
  wertsachen: ['keine Wertsachen', 'Handy', 'Schlüssel', 'Geldbörse', 'Brille', 'Hörgerät', 'Schmuck', 'an Klinik übergeben', 'bei Angehörigen', 'bei Patient/in verblieben'],
  unterlagen: ['Krankenkassenkarte', 'Medikamentenplan', 'Arztbrief', 'Entlassbrief', 'Patientenverfügung', 'Vorsorgevollmacht', 'eigene Medikamente', 'keine Unterlagen vorhanden']
};

const xabcdeOptions = {
  blutung: ['Keine Angabe', 'Keine starke Blutung', 'Starke Blutung kontrolliert', 'Starke Blutung unkontrolliert'],
  atemweg: ['Keine Angabe', 'Frei', 'Gefährdet', 'Verlegt'],
  hws: ['Keine Angabe', 'Keine Immobilisation', 'Stifneck', 'Vakuummatratze'],
  atmung: ['Keine Angabe', 'Unauffällig', 'Dyspnoe', 'Bradypnoe', 'Tachypnoe', 'Apnoe'],
  atemgeraeusche: ['Keine Angabe', 'Beidseits vorhanden', 'Links abgeschwächt', 'Rechts abgeschwächt', 'Keine'],
  sauerstoff: ['Keine', '2 l/min', '4 l/min', '6 l/min', '10 l/min', '15 l/min'],
  haut: ['Keine Angabe', 'Rosig / warm', 'Blass', 'Kalt / schweißig', 'Zyanotisch'],
  rekap: ['Keine Angabe', '< 2 Sekunden', '> 2 Sekunden'],
  pulsqualitaet: ['Keine Angabe', 'Kräftig', 'Schwach', 'Fadenförmig'],
  avpu: ['Keine Angabe', 'A', 'V', 'P', 'U'],
  pupillen: ['Keine Angabe', 'Isokor', 'Anisokor', 'Lichtstarr'],
  bodycheck: ['Keine Angabe', 'Unauffällig', 'Auffällig'],
  befast_balance: ['Keine Angabe', 'Unauffällig', 'Akute Gang-/Standunsicherheit', 'Akuter Schwindel / Ataxie'],
  befast_face: ['Keine Angabe', 'Symmetrisch', 'Fazialisparese links', 'Fazialisparese rechts'],
  befast_speech: ['Keine Angabe', 'Unauffällig', 'Dysarthrie', 'Aphasie', 'Sprachverständnis gestört'],
  befast_eyes: ['Keine Angabe', 'Unauffällig', 'Akute Sehstörung', 'Doppelbilder', 'Gesichtsfeldausfall'],
  befast_arms: ['Keine Angabe', 'Kein Absinken', 'Armabsinken links', 'Armabsinken rechts', 'Armabsinken beidseits']
};

const opqrstOptions = {
  onset: ['', 'Plötzlich', 'Allmählich', 'Progressiv verschlimmernd', 'Wiederkehrend'],
  provocation: ['', 'Bewegung verschlimmert', 'Ruhe lindert', 'Tiefe Atmung verschlimmert', 'Druck lindert', 'Wärme lindert', 'Kälte lindert', 'Nichts lindert'],
  quality: ['', 'Stechend/Messerscharf', 'Dumpf', 'Drückend', 'Reißend', 'Brennend', 'Ziehend', 'Klopfend', 'Rauschhaft'],
  severity_desc: ['', 'Kein Schmerz (0)', 'Minimal (1-3)', 'Mäßig (4-6)', 'Schwer (7-8)', 'Sehr schwer (9-10)'],
  zeitverlauf: ['', 'Konstant', 'Intermittierend', 'Sich verschlimmernd', 'Sich verbessernd', 'Gleichbleibend']
};

const befastNormalValues = new Set(['Unauffällig', 'Symmetrisch', 'Kein Absinken', 'Keine Angabe', '']);

const riskFactorLabels = {
  raucher: 'Raucher',
  alkohol: 'Alkoholkonsum',
  drogen: 'Drogen',
  diabetes: 'Diabetes',
  hypertonie: 'Hypertonie',
  antikoagulation: 'Antikoagulation'
};

const pediatricRiskFactorLabels = {
  fruehgeburtlichkeit: 'Frühgeburtlichkeit',
  angeborene_erkrankung: 'Angeborene Erkrankung',
  chronische_erkrankung_kind: 'Chronische Erkrankung',
  immunsuppression_kind: 'Immunsuppression',
  entwicklungsauffaelligkeit: 'Entwicklungsauffälligkeit',
  relevante_exposition: 'Relevante Exposition im Umfeld'
};

const pediatricGcsOptions = {
  gcs_augen: [['', 'Bitte auswählen'], ['4', '4 – spontan'], ['3', '3 – auf Ansprache'], ['2', '2 – auf Schmerzreiz'], ['1', '1 – keine Reaktion']],
  gcs_verbal: [['', 'Bitte auswählen'], ['5', '5 – altersentsprechend / orientiert'], ['4', '4 – irritabel / verwirrt'], ['3', '3 – anhaltendes Schreien / unpassende Worte'], ['2', '2 – Stöhnen / unverständliche Laute'], ['1', '1 – keine Reaktion']],
  gcs_motorik: [['', 'Bitte auswählen'], ['6', '6 – befolgt Aufforderung / spontan altersgerecht'], ['5', '5 – lokalisiert Schmerz'], ['4', '4 – zieht auf Schmerz zurück'], ['3', '3 – abnorme Beugung'], ['2', '2 – Streckreaktion'], ['1', '1 – keine Reaktion']]
};

const apgarComponents = [
  ['herzfrequenz', 'Herzfrequenz', ['0 – nicht vorhanden', '1 – unter 100/min', '2 – mindestens 100/min']],
  ['atmung', 'Atmung', ['0 – nicht vorhanden', '1 – langsam/unregelmäßig, schwacher Schrei', '2 – regelmäßig, kräftiger Schrei']],
  ['muskeltonus', 'Muskeltonus', ['0 – schlaff', '1 – geringe Beugung', '2 – aktive Bewegung']],
  ['reflexe', 'Reflexantwort', ['0 – keine Reaktion', '1 – Grimassieren', '2 – Husten/Niesen/kräftige Reaktion']],
  ['hautkolorit', 'Hautkolorit', ['0 – blass/blau', '1 – Stamm rosig, Extremitäten blau', '2 – vollständig rosig']]
];

const traumaBodyRegions = {
  kopf: { label: 'Kopf', bones: 'Schädel, Unterkiefer, Gesichtsschädel', vessels: 'A. carotis externa und Äste, oberflächliche Kopfgefäße' },
  gesicht: { label: 'Gesicht', bones: 'Nasenbein, Jochbein, Ober- und Unterkiefer', vessels: 'A. facialis, A. temporalis superficialis' },
  hinterkopf: { label: 'Hinterkopf', bones: 'Hinterhauptbein, Schädelbasis', vessels: 'A. occipitalis, oberflächliche Kopfgefäße' },
  hals: { label: 'Hals', bones: 'Halswirbelsäule, Schlüsselbeinansatz', vessels: 'A. carotis, V. jugularis' },
  schulter_rechts: { label: 'Schulter rechts', bones: 'Clavicula, Scapula, proximaler Humerus', vessels: 'A./V. subclavia und axillaris' },
  schulter_links: { label: 'Schulter links', bones: 'Clavicula, Scapula, proximaler Humerus', vessels: 'A./V. subclavia und axillaris' },
  thorax: { label: 'Brustkorb', bones: 'Rippen, Sternum, Schlüsselbein, Brustwirbelsäule', vessels: 'Aorta thoracica, A./V. subclavia, Interkostalgefäße' },
  thorax_rechts: { label: 'Brustkorb rechts', bones: 'rechte Rippen, Clavicula, Sternum', vessels: 'Interkostalgefäße, A./V. subclavia' },
  thorax_links: { label: 'Brustkorb links', bones: 'linke Rippen, Clavicula, Sternum', vessels: 'Interkostalgefäße, A./V. subclavia' },
  abdomen: { label: 'Bauch', bones: 'untere Rippen, Lendenwirbelsäule', vessels: 'Aorta abdominalis, V. cava inferior, Mesenterialgefäße' },
  abdomen_rechts: { label: 'Bauch rechts', bones: 'untere rechte Rippen, Lendenwirbelsäule', vessels: 'Aorta abdominalis, V. cava inferior, Mesenterialgefäße' },
  abdomen_links: { label: 'Bauch links', bones: 'untere linke Rippen, Lendenwirbelsäule', vessels: 'Aorta abdominalis, V. cava inferior, Mesenterialgefäße' },
  becken: { label: 'Becken', bones: 'Beckenring, Hüftgelenk, Kreuzbein', vessels: 'A./V. iliaca, femorale Gefäßübergänge' },
  oberarm_rechts: { label: 'Oberarm rechts', bones: 'Humerus', vessels: 'A. brachialis, V. basilica und cephalica' },
  oberarm_links: { label: 'Oberarm links', bones: 'Humerus', vessels: 'A. brachialis, V. basilica und cephalica' },
  ellenbogen_rechts: { label: 'Ellenbogen rechts', bones: 'distaler Humerus, Radiuskopf, Ulna', vessels: 'A. brachialis und Ellenbogengefäßnetz' },
  ellenbogen_links: { label: 'Ellenbogen links', bones: 'distaler Humerus, Radiuskopf, Ulna', vessels: 'A. brachialis und Ellenbogengefäßnetz' },
  unterarm_rechts: { label: 'Unterarm rechts', bones: 'Radius und Ulna', vessels: 'A. radialis und ulnaris' },
  unterarm_links: { label: 'Unterarm links', bones: 'Radius und Ulna', vessels: 'A. radialis und ulnaris' },
  hand_rechts: { label: 'Hand rechts', bones: 'Handwurzel, Mittelhand, Fingerknochen', vessels: 'Arcus palmaris, Digitalarterien' },
  hand_links: { label: 'Hand links', bones: 'Handwurzel, Mittelhand, Fingerknochen', vessels: 'Arcus palmaris, Digitalarterien' },
  oberschenkel_rechts: { label: 'Oberschenkel rechts', bones: 'Femur', vessels: 'A./V. femoralis, A. profunda femoris' },
  oberschenkel_links: { label: 'Oberschenkel links', bones: 'Femur', vessels: 'A./V. femoralis, A. profunda femoris' },
  knie_rechts: { label: 'Knie rechts', bones: 'Patella, distaler Femur, Tibiakopf', vessels: 'A./V. poplitea' },
  knie_links: { label: 'Knie links', bones: 'Patella, distaler Femur, Tibiakopf', vessels: 'A./V. poplitea' },
  unterschenkel_rechts: { label: 'Unterschenkel rechts', bones: 'Tibia und Fibula', vessels: 'A. tibialis anterior/posterior, A. fibularis' },
  unterschenkel_links: { label: 'Unterschenkel links', bones: 'Tibia und Fibula', vessels: 'A. tibialis anterior/posterior, A. fibularis' },
  fuss_rechts: { label: 'Fuß rechts', bones: 'Fußwurzel, Mittelfuß, Zehenknochen', vessels: 'A. dorsalis pedis, Plantargefäße' },
  fuss_links: { label: 'Fuß links', bones: 'Fußwurzel, Mittelfuß, Zehenknochen', vessels: 'A. dorsalis pedis, Plantargefäße' },
  arm_links: { label: 'Arm links', bones: 'Humerus, Radius, Ulna, Handknochen', vessels: 'A. axillaris, brachialis, radialis, ulnaris' },
  arm_rechts: { label: 'Arm rechts', bones: 'Humerus, Radius, Ulna, Handknochen', vessels: 'A. axillaris, brachialis, radialis, ulnaris' },
  bein_links: { label: 'Bein links', bones: 'Femur, Patella, Tibia, Fibula, Fußknochen', vessels: 'A. femoralis, poplitea, tibialis' },
  bein_rechts: { label: 'Bein rechts', bones: 'Femur, Patella, Tibia, Fibula, Fußknochen', vessels: 'A. femoralis, poplitea, tibialis' },
  ruecken_oben: { label: 'Oberer Rücken', bones: 'Schulterblatt, Rippen, Brustwirbelsäule', vessels: 'paravertebrale und interkostale Gefäße' },
  ruecken_unten: { label: 'Unterer Rücken', bones: 'Lendenwirbelsäule, Kreuzbein, hinterer Beckenring', vessels: 'Aorta abdominalis/iliakale Gefäße in tiefer Nachbarschaft' },
  gesaess_rechts: { label: 'Gesäß rechts', bones: 'hinterer Beckenring, Hüftgelenk, proximaler Femur', vessels: 'A./V. glutea, tiefer Verlauf des N. ischiadicus' },
  gesaess_links: { label: 'Gesäß links', bones: 'hinterer Beckenring, Hüftgelenk, proximaler Femur', vessels: 'A./V. glutea, tiefer Verlauf des N. ischiadicus' }
};

const traumaInjuryTypes = ['Wunde', 'Blutung', 'Frakturverdacht', 'Luxationsverdacht', 'Prellung/Hämatom', 'Verbrennung', 'Schwellung', 'Druckschmerz', 'Fehlstellung', 'Amputation', 'Fremdkörper'];

function effectiveVitalStatus(vital, statusKey) {
  return vital?.[statusKey] === CUSTOM_STATUS ? vital?.[`${statusKey}_custom`] : vital?.[statusKey];
}

function addProtocolBlock(title, rows) {
  const documented = rows.filter(([, value]) => hasValue(value));
  if (documented.length === 0) return '';
  const lines = [`${title}`, '=================================================='];
  documented.forEach(([label, value]) => lines.push(`${label}: ${value}`));
  return `${lines.join('\n')}\n\n`;
}

function formatObservation(value, status = '', unit = '') {
  const valueText = hasValue(value) ? String(value).trim() : '';
  const statusText = hasValue(status) ? String(status).trim() : '';
  const unitText = unit && valueText ? ` ${unit}` : '';
  if (valueText && statusText) return `${valueText}${unitText} (${statusText})`;
  if (valueText) return `${valueText}${unitText}`;
  return statusText;
}

function formatBloodPressure(vital) {
  if (hasValue(vital.rr_sys) || hasValue(vital.rr_dia)) {
    return formatObservation(`${vital.rr_sys || ''}/${vital.rr_dia || ''}`, effectiveVitalStatus(vital, 'rr_status'), 'mmHg');
  }
  return formatObservation('', effectiveVitalStatus(vital, 'rr_status'));
}

function formatSelectedAllergies(s) {
  if (s.allergien === 'Vorhanden' && hasValue(s.allergien_text)) return `Vorhanden: ${s.allergien_text}`;
  return s.allergien;
}

function formatSelectedMedication(s) {
  if (s.medikamente_option === 'Medikamente eingeben' && hasValue(s.medikamente)) return s.medikamente;
  return s.medikamente_option || s.medikamente;
}

function formatLastMeal(s) {
  if (s.letzte_mahlzeit === 'Eigene Eingabe' && hasValue(s.letzte_mahlzeit_text)) return s.letzte_mahlzeit_text;
  return s.letzte_mahlzeit || s.letzte_aufnahme;
}

function formatRiskFactors(s) {
  const risks = Object.entries({ ...riskFactorLabels, ...pediatricRiskFactorLabels })
    .filter(([key]) => Boolean(s[key]))
    .map(([, label]) => label);
  if (hasValue(s.risiken_sonstige)) risks.push(s.risiken_sonstige);
  if (hasValue(s.risikofaktoren)) risks.push(s.risikofaktoren);
  return risks.join(', ');
}

function formatPregnancyStatus(s) {
  return s.schwangerschaft === 'Nicht relevant' ? '' : s.schwangerschaft;
}

function documentedVitalStatusValues(patient) {
  const vital = patient?.vitalwerte || {};
  return [
    effectiveVitalStatus(vital, 'rr_status'),
    effectiveVitalStatus(vital, 'puls_status'),
    effectiveVitalStatus(vital, 'spo2_status'),
    effectiveVitalStatus(vital, 'af_status'),
    effectiveVitalStatus(vital, 'bz_status'),
    effectiveVitalStatus(vital, 'temperatur_status'),
    effectiveVitalStatus(vital, 'gcs_status')
  ].filter(hasValue).map((item) => String(item));
}

function protocolContainsVitalStatuses(protocolText, patient) {
  const values = documentedVitalStatusValues(patient);
  if (values.length === 0) return true;
  const text = String(protocolText || '');
  return values.every((value) => text.includes(value));
}

function renderListBlock(title, items, formatter) {
  const lines = (Array.isArray(items) ? items : []).map(formatter).filter(hasValue);
  if (lines.length === 0) return '';
  return `${title}\n==================================================\n${lines.map((line) => `- ${line}`).join('\n')}\n\n`;
}

function compactJoin(values, separator = ', ') {
  return values.filter(hasValue).map((value) => String(value).trim()).join(separator);
}

function addProtocolParagraph(title, sentences) {
  const lines = sentences.filter(hasValue).map((value) => String(value).trim());
  if (lines.length === 0) return '';
  return `${title}\n==================================================\n${lines.join(' ')}\n\n`;
}

function patientIdentity(vital) {
  return compactJoin([
    vital.geschlecht,
    hasValue(vital.alter) ? `${vital.alter} Jahre` : ''
  ]) || 'Patientendaten nicht vollständig dokumentiert';
}

function symptomSummary(vital, samplers, opqrst) {
  if (hasValue(vital.kurzbericht)) return vital.kurzbericht;
  if (hasValue(samplers.symptome)) return samplers.symptome;
  return compactJoin([
    opqrst.region,
    opqrst.quality,
    hasValue(opqrst.nrs) ? `NRS ${opqrst.nrs}/10` : ''
  ]);
}

function actionLines(measures) {
  const timeline = Array.isArray(measures.timeline) ? measures.timeline : [];
  const medication = Array.isArray(measures.medikation) ? measures.medikation : [];
  return [
    ...timeline.map((item) => {
      const row = item || {};
      return `${row.zeit || ''} - ${row.massnahme || ''}`.trim();
    }),
    ...medication.map((item) => {
      const row = item || {};
      return `${row.zeit || ''} - ${row.medikament || row.name || ''} ${row.dosis || ''} ${row.weg || ''}`.trim();
    })
  ].filter(hasValue);
}

function reanimationLines(reanimation) {
  const shocks = Array.isArray(reanimation.shocks) ? reanimation.shocks : [];
  const lines = [
    reanimation.active ? 'Reanimation durchgeführt' : '',
    compactJoin([
      hasValue(reanimation.cpr_start) ? `CPR-Beginn ${reanimation.cpr_start}` : '',
      hasValue(reanimation.cpr_end) ? `CPR-Ende/Übergabe ${reanimation.cpr_end}` : '',
      hasValue(reanimation.initial_rhythm) ? `Initialrhythmus ${reanimation.initial_rhythm}` : ''
    ], '; '),
    compactJoin([
      hasValue(reanimation.rosc) ? `ROSC ${reanimation.rosc}` : '',
      hasValue(reanimation.rosc_time) ? `ROSC-Zeit ${reanimation.rosc_time}` : ''
    ], '; '),
    compactJoin([
      hasValue(reanimation.no_flow) ? `No-flow ${reanimation.no_flow}` : '',
      hasValue(reanimation.low_flow) ? `Low-flow ${reanimation.low_flow}` : '',
      reanimation.mechanical_cpr ? 'mechanische Reanimationshilfe eingesetzt' : ''
    ], '; '),
    hasValue(reanimation.airway) ? `Atemweg/Beatmung: ${reanimation.airway}` : '',
    hasValue(reanimation.access) ? `Zugang: ${reanimation.access}` : '',
    hasValue(reanimation.meds) ? `Medikamente während CPR: ${reanimation.meds}` : '',
    compactJoin([
      hasValue(reanimation.notarzt_alarm) ? `Notarzt alarmiert ${reanimation.notarzt_alarm}` : '',
      hasValue(reanimation.notarzt_arrival) ? `eingetroffen ${reanimation.notarzt_arrival}` : '',
      hasValue(reanimation.notarzt_takeover) ? `Übernahme ${reanimation.notarzt_takeover}` : ''
    ], '; '),
    hasValue(reanimation.outcome) ? `Ausgang: ${reanimation.outcome}` : '',
    hasValue(reanimation.notes) ? `Notizen: ${reanimation.notes}` : ''
  ].filter(hasValue);

  const shockLines = shocks.map((item, index) => {
    const shock = item || {};
    return compactJoin([
      `${index + 1}. Schock`,
      hasValue(shock.zeit) ? shock.zeit : '',
      hasValue(shock.energie) ? `${shock.energie} J` : '',
      shock.rhythmus
    ], ' - ');
  }).filter(hasValue);

  return [...lines, ...shockLines];
}

function sinnhaftRows(patient) {
  const vital = patient.vitalwerte || {};
  const x = patient.xabcde || {};
  const s = patient.samplers || {};
  const o = patient.opqrst || {};
  const psyche = patient.psyche || {};
  const amls = patient.amls || {};
  const measures = patient.massnahmen || {};
  const reanimation = patient.reanimation || {};
  const handover = patient.uebergabe || {};
  const priority = compactJoin([
    hasValue(formatBloodPressure(vital)) ? `RR ${formatBloodPressure(vital)}` : '',
    hasValue(vital.puls) ? `Puls ${formatObservation(vital.puls, effectiveVitalStatus(vital, 'puls_status'), '/min')}` : '',
    hasValue(vital.spo2) ? `SpO2 ${formatObservation(vital.spo2, effectiveVitalStatus(vital, 'spo2_status'), '%')}` : '',
    hasValue(vital.gcs) ? `GCS ${formatObservation(vital.gcs, effectiveVitalStatus(vital, 'gcs_status'), '/15')}` : '',
    hasValue(x.atemweg) ? `Atemweg ${x.atemweg}` : '',
    hasValue(x.atmung) ? `Atmung ${x.atmung}` : '',
    hasValue(x.haut) ? `Kreislauf ${x.haut}` : '',
    hasValue(x.avpu) ? `AVPU ${x.avpu}` : ''
  ]);
  const anamnesis = compactJoin([
    hasValue(formatSelectedAllergies(s)) ? `Allergien: ${formatSelectedAllergies(s)}` : '',
    hasValue(formatSelectedMedication(s)) ? `Medikation: ${formatSelectedMedication(s)}` : '',
    hasValue(s.vorgeschichte) ? `Vorgeschichte: ${s.vorgeschichte}` : '',
    hasValue(formatLastMeal(s)) ? `Letzte Mahlzeit: ${formatLastMeal(s)}` : '',
    hasValue(formatRiskFactors(s)) ? `Risiken: ${formatRiskFactors(s)}` : ''
  ], '; ');
  return [
    ['S Start', handover.sinnhaft_start || 'Ruhe herstellen, Face-to-Face-Übergabe, Manipulationen am Patienten möglichst pausieren.'],
    ['I Identifikation', handover.sinnhaft_identifikation || patientIdentity(vital)],
    ['N Notfallereignis', handover.sinnhaft_notfallereignis || compactJoin([symptomSummary(vital, s, o), s.ereignis], '; ')],
    ['N Notfallpriorität', handover.sinnhaft_notfallprioritaet || priority],
    ['H Handlung', handover.sinnhaft_handlung || actionLines(measures).join('; ')],
    ['A Anamnese', handover.sinnhaft_anamnese || anamnesis],
    ['F Fazit', handover.sinnhaft_fazit || compactJoin([amls.arbeitsdiagnose, handover.ziel], ' -> ')],
    ['T Teamfragen', handover.sinnhaft_teamfragen]
  ];
}

function generateLocalProtocolText(patient) {
  const crew = patient.besatzung || {};
  const vital = patient.vitalwerte || {};
  const x = patient.xabcde || {};
  const s = patient.samplers || {};
  const o = patient.opqrst || {};
  const amls = patient.amls || {};
  const measures = patient.massnahmen || {};
  const reanimation = patient.reanimation || {};
  const handover = patient.uebergabe || {};
  let text = 'RD-PROTOKOLL - DOKUMENTATIONSENTWURF\n';
  text += '==================================================\n';
  text += `Lokal erzeugt am ${new Date().toLocaleString('de-DE')}\n`;
  text += 'Enthält ausschließlich dokumentierte Angaben; vor Verwendung vollständig prüfen.\n\n';
  text += addProtocolBlock('BESATZUNG / SCHICHT', [
    ['Transportführer/in', crew.verantwortlicher],
    ['Fahrer/in', crew.fahrer],
    ['Azubi', crew.azubi],
    ['Praktikant/in', crew.praktikant],
  ]);
  const symptom = symptomSummary(vital, s, o);
  text += addProtocolParagraph('EINSATZBERICHT', [
    hasValue(symptom)
      ? `Bei ${patientIdentity(vital)} wurde präklinisch folgendes Hauptproblem dokumentiert: ${symptom}.`
      : `Bei ${patientIdentity(vital)} wurde ein Rettungsdiensteinsatz dokumentiert; ein Kurzbericht ist noch nicht hinterlegt.`,
    hasValue(amls.arbeitsdiagnose) ? `Als Arbeitsdiagnose/Verdacht wurde ${amls.arbeitsdiagnose} festgehalten.` : ''
  ]);
  text += addProtocolParagraph('ERSTBEFUND UND VERLAUF', [
    compactJoin([
      hasValue(formatBloodPressure(vital)) ? `RR ${formatBloodPressure(vital)}` : '',
      hasValue(vital.puls) ? `Puls ${formatObservation(vital.puls, effectiveVitalStatus(vital, 'puls_status'), '/min')}` : '',
      hasValue(vital.spo2) ? `SpO2 ${formatObservation(vital.spo2, effectiveVitalStatus(vital, 'spo2_status'), '%')}` : '',
      hasValue(vital.gcs) ? `GCS ${formatObservation(vital.gcs, effectiveVitalStatus(vital, 'gcs_status'), '/15')}` : ''
    ]),
    compactJoin([
      hasValue(x.blutung) ? `xABCDE: X ${x.blutung}` : '',
      hasValue(x.atemweg) ? `A ${x.atemweg}` : '',
      hasValue(x.atmung) ? `B ${x.atmung}` : '',
      hasValue(x.haut) ? `C ${x.haut}` : '',
      hasValue(x.avpu) ? `D AVPU ${x.avpu}` : '',
      hasValue(x.bodycheck) ? `E ${x.bodycheck}` : ''
    ])
  ]);
  text += addProtocolParagraph('MAßNAHMEN UND WIRKUNG', [actionLines(measures).join('; ') || 'Keine Maßnahmen/Medikationen dokumentiert.']);
  text += addProtocolParagraph('REANIMATION', reanimationLines(reanimation));
  text += addProtocolBlock('VITALWERTE & DEMOGRAPHIE', [
    ['Alter', vital.alter],
    ['Geschlecht', vital.geschlecht],
    ['RR', formatBloodPressure(vital)],
    ['Puls', formatObservation(vital.puls, effectiveVitalStatus(vital, 'puls_status'), '/min')],
    ['SpO2', formatObservation(vital.spo2, effectiveVitalStatus(vital, 'spo2_status'), '%')],
    ['Atemfrequenz', formatObservation(vital.af, effectiveVitalStatus(vital, 'af_status'), '/min')],
    ['BZ', formatObservation(vital.bz, effectiveVitalStatus(vital, 'bz_status'), 'mg/dL')],
    ['Temperatur', formatObservation(vital.temperatur, effectiveVitalStatus(vital, 'temperatur_status'), '°C')],
    ['GCS', formatObservation(vital.gcs, effectiveVitalStatus(vital, 'gcs_status'), '/15')],
    ['Kurzbericht', vital.kurzbericht],
  ]);
  text += addProtocolBlock('xABCDE', [
    ['X Blutung', x.blutung],
    ['Blutung Lokalisation', x.blutung_lokalisation],
    ['A Atemweg', x.atemweg],
    ['HWS', x.hws],
    ['B Atmung', x.atmung],
    ['Atemgeräusche', x.atemgeraeusche],
    ['Sauerstoff', x.sauerstoff],
    ['C Hautzeichen', x.haut],
    ['Rekapillarisierungszeit', x.rekap],
    ['Pulsqualität', x.pulsqualitaet],
    ['D AVPU', x.avpu],
    ['Pupillen', x.pupillen],
    ['E Bodycheck', x.bodycheck],
    ['Auffälligkeiten', x.bodycheck_text],
    ['Unterkühlung', x.unterkuehlung ? 'Ja' : ''],
    ['Verbrennung', x.verbrennung ? 'Ja' : ''],
    ['BE-FAST Balance', x.befast_balance],
    ['BE-FAST Eyes', x.befast_eyes],
    ['BE-FAST Face', x.befast_face],
    ['BE-FAST Arms', x.befast_arms],
    ['BE-FAST Speech', x.befast_speech],
    ['BE-FAST Time', x.befast_time],
  ]);
  text += renderListBlock('Trauma-Lokalisationen', x.trauma_befunde, (item) => {
    const region = traumaBodyRegions[item?.region]?.label || item?.region || '';
    return `${region} (${item?.side || ''}): ${compactJoin([...(item?.verletzungsarten || []), item?.blutung ? `Blutung ${item.blutung}` : '', item?.notiz], '; ')}`;
  });
  text += addProtocolBlock('SAMPLERS', [
    ['Symptome', s.symptome],
    ['Allergien', formatSelectedAllergies(s)],
    ['Medikamente', formatSelectedMedication(s)],
    ['Vorgeschichte', s.vorgeschichte],
    ['Letzte Mahlzeit', formatLastMeal(s)],
    ['Letzte Medikamenteneinnahme', s.letzte_medikamenteneinnahme],
    ['Letzter Stuhlgang', s.letzter_stuhlgang],
    ['Letzte Miktion', s.letzte_miktion],
    ['Letztes Erbrechen', s.letztes_erbrechen],
    ['Ereignis', s.ereignis],
    ['Traumamechanismus', s.trauma_mechanismus],
    ['Sturzhöhe Kategorie', s.sturzhoehe_kategorie],
    ['Sturzhöhe Meter', s.sturzhoehe_meter],
    ['Aufprallfläche', s.aufprallflaeche],
    ['Aufprallrichtung/Körperposition', s.aufprallrichtung],
    ['Schutzsysteme', s.schutzsysteme],
    ['Trauma-Besonderheiten', s.trauma_besonderheiten],
    ['Risikofaktoren', formatRiskFactors(s)],
    ['Schwangerschaft', formatPregnancyStatus(s)],
    ['Sonstiges', s.sonstiges],
  ]);
  text += addProtocolBlock('OPQRST', [
    ['Schmerz vorhanden', o.schmerz_vorhanden],
    ['Onset', o.onset],
    ['Onset Zusatz', o.onset_text],
    ['Provocation/Palliation', o.provocation],
    ['Provocation Zusatz', o.provocation_text],
    ['Quality', o.quality],
    ['Quality Zusatz', o.quality_text],
    ['Region/Radiation', o.region],
    ['Ausstrahlung', o.radiation],
    ['NRS', o.nrs || o.severity],
    ['Severity Beschreibung', o.severity_desc],
    ['Zeitverlauf', o.zeitverlauf || o.time],
    ['Dauer', o.dauer],
  ]);
  text += addProtocolBlock('PSYCHE / PSYCHKG NRW', [
    ['Psychischer Zustand', psyche.zustand],
    ['Orientierung', psyche.orientierung],
    ['Verhalten / Kooperation', psyche.kooperation],
    ['Suizidalität', psyche.suizidalitaet],
    ['Eigengefährdung', psyche.eigengefaehrdung],
    ['Fremdgefährdung', psyche.fremdgefaehrdung],
    ['Einwilligungsfähigkeit', psyche.einwilligungsfaehigkeit],
    ['Aufnahme / Unterbringungsweg', psyche.unterbringungsweg],
    ['Veranlasst durch', psyche.veranlasst_durch],
    ['Ärztliches Zeugnis / Beschluss', psyche.nachweis],
    ['Zielklinik', psyche.zielklinik],
    ['Begleitung / Sicherung', psyche.begleitung],
    ['Begründung / konkrete Beobachtungen', psyche.begruendung],
    ['Weitere Notizen', psyche.notizen],
  ]);
  text += addProtocolBlock('DIAGNOSEHILFE / VERDACHTSDIAGNOSTIK', [
    ['Leitsymptom', amls.leitsymptom],
    ['Arbeitsdiagnose', amls.arbeitsdiagnose],
    ['Notizen/Begründung', amls.notizen],
  ]);
  text += renderListBlock('Differenzialdiagnosen / Kandidaten', amls.custom_candidates, (item) => {
    const candidate = typeof item === 'string' ? { diagnose: item } : item || {};
    return [candidate.diagnose || candidate.name, candidate.hinweis || candidate.rationale].filter(hasValue).join(': ');
  });
  text += renderListBlock('Zurückgestellte Diagnosen', amls.excluded, (item) => {
    const excluded = typeof item === 'string' ? { diagnose: item } : item || {};
    return [excluded.diagnose || excluded.name, excluded.begruendung || excluded.rationale].filter(hasValue).join(': ');
  });
  text += renderListBlock('MAßNAHMEN', measures.timeline, (item) => `${item.zeit || ''} - ${item.massnahme || ''}`.trim());
  text += renderListBlock('MEDIKATION', measures.medikation, (item) => `${item.zeit || ''} - ${item.medikament || ''} ${item.dosis || ''} ${item.weg || ''}`.trim());
  text += addProtocolBlock('REANIMATION', [
    ['Durchgeführt', reanimation.active ? 'Ja' : ''],
    ['CPR-Beginn', reanimation.cpr_start],
    ['CPR-Ende / Übergabe', reanimation.cpr_end],
    ['Initialrhythmus', reanimation.initial_rhythm],
    ['ROSC', reanimation.rosc],
    ['ROSC-Zeit', reanimation.rosc_time],
    ['No-flow-Zeit', reanimation.no_flow],
    ['Low-flow-Zeit', reanimation.low_flow],
    ['Mechanische Reanimationshilfe', reanimation.mechanical_cpr ? 'Ja' : ''],
    ['Atemweg / Beatmung', reanimation.airway],
    ['Zugang', reanimation.access],
    ['Medikamente während CPR', reanimation.meds],
    ['Notarzt alarmiert', reanimation.notarzt_alarm],
    ['Notarzt eingetroffen', reanimation.notarzt_arrival],
    ['Notarzt übernimmt', reanimation.notarzt_takeover],
    ['Ausgang', reanimation.outcome],
    ['Notizen', reanimation.notes],
  ]);
  text += renderListBlock('DEFIBRILLATIONEN', reanimation.shocks, (item, index) => {
    const shock = item || {};
    return compactJoin([
      `${index + 1}. Schock`,
      shock.zeit,
      hasValue(shock.energie) ? `${shock.energie} J` : '',
      shock.rhythmus
    ], ' - ');
  });
  text += addProtocolBlock('SINNHAFT-ÜBERGABE', sinnhaftRows(patient));
  text += addProtocolBlock('ÜBERGABE', [
    ['Ziel', handover.ziel],
    ['Text', handover.text],
    ['Lagerung / Transfertechnik', handover.lagerung],
    ['Wertsachen / Eigentum', handover.wertsachen],
    ['Krankenkassenkarte', handover.krankenkassenkarte],
    ['Patientenunterlagen / Medikamente', handover.unterlagen],
    ['Begleitperson / Angehörige', handover.begleitperson],
    ['Besonderheiten bei Übergabe', handover.besonderheiten],
  ]);
  return text.trim();
}

function valueOrBlank(value, blank = '__________') {
  return hasValue(value) ? String(value).trim() : blank;
}

function buildRefusalScope(refusal) {
  if (hasValue(refusal.scope)) return String(refusal.scope).trim();
  const scopes = [];
  if (refusal.refuse_treatment) scopes.push('die weitere rettungsdienstliche Behandlung');
  if (refusal.refuse_transport) scopes.push('den empfohlenen Transport');
  if (scopes.length === 2) return `${scopes[0]} und ${scopes[1]}`;
  if (scopes.length === 1) return scopes[0];
  return valueOrBlank(refusal.scope, 'die weitere rettungsdienstliche Behandlung und/oder den empfohlenen Transport');
}

function buildPatientRefusalText(patient, refusal) {
  const vital = patient?.vitalwerte || {};
  const einsatz = patient?.einsatz || {};
  const identityParts = [];
  if (hasValue(vital.geschlecht)) identityParts.push(vital.geschlecht);
  if (hasValue(vital.alter)) identityParts.push(`${vital.alter} Jahre`);
  const identity = identityParts.length ? ` (${identityParts.join(', ')})` : '';
  const patientName = valueOrBlank(refusal.patient_name);
  const presentedTo = valueOrBlank(refusal.presented_to);
  const caseNumber = valueOrBlank(refusal.case_number || einsatz.einsatznummer);
  const dateText = valueOrBlank(refusal.date);
  const timeText = valueOrBlank(refusal.time);
  const scope = buildRefusalScope(refusal);
  const reason = valueOrBlank(refusal.reason);
  const risks = valueOrBlank(refusal.risks, 'Verschlechterung des Gesundheitszustands, verzögerte Diagnostik/Therapie, bleibende Gesundheitsschäden bis hin zu akuter Lebensgefahr');
  const witness = valueOrBlank(refusal.witness);
  const capacityText = refusal.capacity_confirmed
    ? 'Der/die Patient/in wirkte zum Zeitpunkt der Entscheidung, soweit rettungsdienstlich beurteilbar, wach, ansprechbar, orientiert, situationsadäquat und einwilligungsfähig.'
    : 'Zur Einwilligungsfähigkeit bestanden Auffälligkeiten bzw. Einschränkungen; diese sind gesondert im Einsatzprotokoll zu dokumentieren.';
  const adviceText = refusal.advised_against
    ? 'Die Ablehnung erfolgte gegen den ausdrücklichen Rat des Rettungsdienstes.'
    : 'Ein ausdrücklicher gegenteiliger Rat des Rettungsdienstes wurde nicht dokumentiert.';
  const signatureText = refusal.signature_refused
    ? 'Patient/in verweigert die Unterschrift; Vermerk und Zeuge/Zeugin siehe unten.'
    : 'Patient/in wurde um Unterschrift gebeten.';

  return [
    'Dokumentation einer Behandlungs-/Transportverweigerung',
    '',
    `Der/die Patient/in ${patientName}${identity} wurde am ${dateText} um ${timeText} Uhr im Rahmen des Rettungsdiensteinsatzes ${caseNumber} durch den Rettungsdienst untersucht, beraten und über das weitere empfohlene Vorgehen aufgeklärt.`,
    `Eine Vorstellung oder Rücksprache erfolgte bei/mit: ${presentedTo}.`,
    '',
    `Der/die Patient/in lehnt trotz Empfehlung des Rettungsdienstes ${scope} ab. Als Grund wurde angegeben: ${reason}.`,
    '',
    `Die Aufklärung erfolgte in verständlicher Form. Besprochen wurden insbesondere die erhobenen Befunde bzw. die Verdachtslage, die empfohlene weitere Abklärung/Behandlung sowie die möglichen Folgen der Ablehnung: ${risks}. Es wurde ausdrücklich darauf hingewiesen, dass derzeit nicht sicher ausgeschlossen werden kann, dass eine ernsthafte oder lebensbedrohliche Erkrankung vorliegt oder sich im weiteren Verlauf entwickelt.`,
    '',
    'Dem/der Patient/in wurde empfohlen, sich zeitnah ärztlich vorstellen zu lassen bzw. den empfohlenen Transport wahrzunehmen. Bei erneuten, anhaltenden oder zunehmenden Beschwerden, Verschlechterung des Allgemeinzustands, Schmerzen, Atemnot, neurologischen Auffälligkeiten, Bewusstseinsveränderung oder Unsicherheit soll unverzüglich erneut der Notruf 112 bzw. ärztliche Hilfe verständigt werden.',
    '',
    `${capacityText} ${adviceText} Die Entscheidung wurde nach erneuter Nachfrage aus freiem Willen geäußert; eine weitere Hilfeleistung bzw. ein Transport wurde erneut angeboten.`,
    '',
    signatureText,
    '',
    `Zeuge/Zeugin: ${witness}`,
    'Unterschrift Patient/in: __________',
    'Unterschrift Rettungsdienst: __________',
    'Falls Unterschrift verweigert: Vermerk/Zeuge: __________'
  ].join('\n');
}

function buildCancellationText(cancellation) {
  const reason = valueOrBlank(cancellation.reason);
  const dateText = valueOrBlank(cancellation.date);
  const timeText = valueOrBlank(cancellation.time);
  const caseNumber = valueOrBlank(cancellation.case_number);
  const location = valueOrBlank(cancellation.location);
  const unit = valueOrBlank(cancellation.unit);
  const dispatcher = valueOrBlank(cancellation.dispatcher);
  const patientContact = valueOrBlank(cancellation.patient_contact);
  const alternative = valueOrBlank(cancellation.alternative_action);
  const details = valueOrBlank(cancellation.details);
  const documentedBy = valueOrBlank(cancellation.documented_by);

  return [
    'Dokumentation Einsatzabbruch / nicht durchgeführter Einsatz',
    '',
    `Der Rettungsdiensteinsatz mit der Einsatznummer ${caseNumber} wurde am ${dateText} um ${timeText} Uhr für das Rettungsmittel ${unit} dokumentiert.`,
    `Einsatzort / Bereich: ${location}.`,
    '',
    `Der Einsatz wurde nicht regulär durchgeführt bzw. vorzeitig beendet. Grund: ${reason}.`,
    `Patientenkontakt: ${patientContact}.`,
    '',
    `Leitstelle / Rücksprache: ${dispatcher}.`,
    `Weitere Veranlassung / Ersatzmaßnahme: ${alternative}.`,
    '',
    `Freitext / Verlauf: ${details}.`,
    '',
    'Die Dokumentation beschreibt den Grund des Abbruchs bzw. der Nichtdurchführbarkeit aus Sicht des Rettungsdienstes zum Zeitpunkt des Ereignisses. Relevante Rückmeldungen an Leitstelle, Führungskraft, Technik oder andere beteiligte Stellen sind ergänzend zu dokumentieren.',
    '',
    `Dokumentiert durch: ${documentedBy}`,
    'Unterschrift / Kürzel Rettungsdienst: __________'
  ].join('\n');
}

function readCookie(name) {
  const prefix = `${name}=`;
  return document.cookie
    .split(';')
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix))
    ?.slice(prefix.length) || '';
}

function isUnsafeMethod(method = 'GET') {
  return !['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(String(method || 'GET').toUpperCase());
}

function api(path, options = {}, token = '') {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers ?? {})
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (!token && isUnsafeMethod(options.method)) {
    const csrf = readCookie('nana_csrf');
    if (csrf) headers['X-NANA-CSRF'] = csrf;
  }
  return fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' })
    .then(async (response) => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 401) {
          window.dispatchEvent(new CustomEvent('nana-session-expired', { detail: { message: data.detail || 'Sitzung abgelaufen.' } }));
        }
        if (response.status === 404 && data.detail === 'Not Found') {
          throw new Error(`API-Endpunkt nicht gefunden: ${API_BASE || window.location.origin}${path}. Bitte NANA neu starten, damit Backend und App dieselbe Version nutzen.`);
        }
        throw new Error(data.detail || 'Anfrage fehlgeschlagen');
      }
      return data;
    })
    .catch((err) => {
      if (err instanceof TypeError) {
        throw new Error('Backend nicht erreichbar. Lokale Entwürfe bleiben im Browser erhalten.');
      }
      throw err;
    });
}

async function fileRequest(path, options = {}, token = '') {
  const headers = { ...(options.headers ?? {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (!token && isUnsafeMethod(options.method)) {
    const csrf = readCookie('nana_csrf');
    if (csrf) headers['X-NANA-CSRF'] = csrf;
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent('nana-session-expired', { detail: { message: data.detail || 'Sitzung abgelaufen.' } }));
    }
    if (response.status === 404 && data.detail === 'Not Found') {
      throw new Error(`API-Endpunkt nicht gefunden: ${API_BASE || window.location.origin}${path}. Bitte NANA neu starten.`);
    }
    throw new Error(data.detail || 'Datei konnte nicht erstellt werden');
  }
  const disposition = response.headers.get('Content-Disposition') || '';
  const filenameMatch = disposition.match(/filename="([^"]+)"/);
  return {
    blob: await response.blob(),
    filename: filenameMatch?.[1] || 'nana-protokoll.pdf'
  };
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function printBlob(blob) {
  const url = URL.createObjectURL(blob);
  const printWindow = window.open(url, '_blank', 'noopener,noreferrer');
  if (printWindow) {
    printWindow.addEventListener('load', () => printWindow.print(), { once: true });
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function printTextDocument(title, text) {
  const escapedTitle = String(title || '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const escapedText = String(text || '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const htmlDocument = `
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <title>${escapedTitle}</title>
        <style>
          @page { margin: 14mm; }
          body { font-family: Arial, Helvetica, sans-serif; color: #111; line-height: 1.35; font-size: 11pt; }
          h1 { font-size: 16pt; margin: 0 0 12px; }
          pre { white-space: pre-wrap; font-family: Arial, Helvetica, sans-serif; margin: 0; }
        </style>
      </head>
      <body>
        <h1>${escapedTitle}</h1>
        <pre>${escapedText}</pre>
      </body>
    </html>
  `;
  const blob = new Blob([htmlDocument], { type: 'text/html;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const printWindow = window.open(url, '_blank', 'noopener,noreferrer');
  if (!printWindow) {
    URL.revokeObjectURL(url);
    return false;
  }
  printWindow.addEventListener('load', () => {
    printWindow.print();
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  }, { once: true });
  return true;
}

function SystemStatus({ online, backendOnline, lastSync }) {
  const state = !online ? 'offline' : backendOnline ? 'online' : 'limited';
  const label = !online ? 'Offline' : backendOnline ? 'Backend verbunden' : 'Backend nicht erreichbar';
  return (
    <div className={`system-status system-${state}`}>
      <span>{label}</span>
      <small>{lastSync ? `Letzter Sync: ${lastSync}` : 'Noch kein Sync in dieser Sitzung'}</small>
    </div>
  );
}

function UserMenu({ session, employee, onLogout }) {
  const [open, setOpen] = useState(false);
  const [activePanel, setActivePanel] = useState('');
  const [announcements, setAnnouncements] = useState({ patch_notes: [], planned_updates: [], feedback: [] });
  const [feedbackDraft, setFeedbackDraft] = useState({ kind: 'Bug', title: '', message: '' });
  const [seenPatchSignature, setSeenPatchSignature] = useState(() => {
    try {
      return localStorage.getItem(`nana_seen_patch_notes_${employee?.id || 'unknown'}`) || '';
    } catch {
      return '';
    }
  });
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');

  async function loadAnnouncements(nextPanel = activePanel || 'patch') {
    setError('');
    try {
      const data = await api('/api/announcements', {}, session.token);
      const previousSignature = (() => {
        try {
          return localStorage.getItem(`nana_seen_patch_notes_${employee?.id || 'unknown'}`) || '';
        } catch {
          return '';
        }
      })();
      const nextSignature = announcementSignature(data.patch_notes);
      setAnnouncements(data);
      setSeenPatchSignature(previousSignature);
      setActivePanel(nextPanel);
      setOpen(true);
      if (nextPanel === 'patch' && nextSignature) {
        try {
          localStorage.setItem(`nana_seen_patch_notes_${employee?.id || 'unknown'}`, nextSignature);
        } catch {
          // Local storage is optional; patch notes still render without it.
        }
      }
    } catch (err) {
      setError(err.message);
      setOpen(true);
    }
  }

  async function submitFeedback(event) {
    event.preventDefault();
    setError('');
    setStatusText('');
    try {
      await api('/api/feedback', {
        method: 'POST',
        body: JSON.stringify(feedbackDraft)
      }, session.token);
      setFeedbackDraft({ kind: 'Bug', title: '', message: '' });
      setStatusText('Meldung wurde an den Adminfeed gesendet.');
      await loadAnnouncements('feedback');
    } catch (err) {
      setError(err.message);
    }
  }

  const visibleList = activePanel === 'planned' ? announcements.planned_updates : announcements.patch_notes;
  const latestPatchSignature = announcementSignature(announcements.patch_notes);
  const hasUnseenPatch = Boolean(latestPatchSignature && latestPatchSignature !== seenPatchSignature);

  return (
    <div className="user-menu">
      <button
        className="user-name-button"
        type="button"
        onClick={() => {
          if (!open) loadAnnouncements('patch');
          setOpen((current) => !current);
        }}
      >
        <span className="user-avatar">{(employee?.name || 'P').trim().charAt(0).toUpperCase()}</span>
        <span>{employee?.name || 'Profil'}</span>
        <ChevronDown className={open ? 'user-menu-chevron open' : 'user-menu-chevron'} size={16} />
      </button>
      {open && (
        <div className="user-dropdown">
          <div className="user-dropdown-head">
            <div>
              <span>Neuigkeiten & Feedback</span>
              <strong>Was gibt es Neues?</strong>
            </div>
          </div>
          <div className="user-dropdown-tabs">
            <button type="button" className={activePanel === 'patch' ? 'active' : ''} onClick={() => loadAnnouncements('patch')}>
              <Megaphone size={17} /><span>Patch Notes</span>{hasUnseenPatch && <em>Neu</em>}
            </button>
            <button type="button" className={activePanel === 'planned' ? 'active' : ''} onClick={() => loadAnnouncements('planned')}><Wrench size={17} /><span>Geplant</span></button>
            <button type="button" className={activePanel === 'privacy' ? 'active' : ''} onClick={() => loadAnnouncements('privacy')}><ShieldCheck size={17} /><span>Datenschutz</span></button>
            <button type="button" className={activePanel === 'feedback' ? 'active' : ''} onClick={() => loadAnnouncements('feedback')}><MessageSquare size={17} /><span>Feedback</span></button>
          </div>
          {error && <div className="error-box compact-box">{error}</div>}
          {statusText && <div className="success-box compact-box">{statusText}</div>}

          {(activePanel === 'patch' || activePanel === 'planned') && (
            <div className="user-dropdown-list">
              {visibleList.length === 0 ? (
                <p className="muted">Noch keine Einträge vorhanden.</p>
              ) : visibleList.map((item, index) => (
                <article className={`dropdown-entry${activePanel === 'patch' && index === 0 && hasUnseenPatch ? ' entry-new' : ''}`} key={item.id || `${item.title}-${item.published_at}`}>
                  <strong>{item.title}</strong>
                  <span>{item.published_at}{activePanel === 'patch' && index === 0 && hasUnseenPatch ? ' · Neu seit deinem letzten Blick' : ''}</span>
                  <p>{item.body}</p>
                </article>
              ))}
            </div>
          )}

          {activePanel === 'privacy' && (
            <div className="privacy-concept">
              <article className="privacy-concept-hero">
                <strong>Datenschutzkonzept NANA</strong>
                <span>Arbeitsstand fuer Betrieb, Pilotierung und Freigabe durch Datenschutzbeauftragte/Träger.</span>
              </article>
              <div className="privacy-concept-grid">
                <article>
                  <h3>1. Zweck und Geltungsbereich</h3>
                  <p>NANA dient der rettungsdienstlichen Einsatzdokumentation, Nachbearbeitung, Qualitätssicherung und dem kontrollierten Export von Einsatzprotokollen. Das Konzept gilt fuer Web-App, Backend, Datenbank, PDF-/Druckfunktionen, Leitstellenimport, Kartenlinks, Benutzerverwaltung und Auditierung.</p>
                </article>
                <article>
                  <h3>2. Verantwortlichkeiten</h3>
                  <p>Der jeweilige Betreiber/Träger ist Verantwortlicher im Sinne der DSGVO. NANA verarbeitet Daten nur als eingesetztes Werkzeug. Administratoren verwalten Konten, Rollen, Aufbewahrung und technische Einstellungen; Einsatzkräfte dokumentieren nur einsatzbezogene Daten.</p>
                </article>
                <article>
                  <h3>3. Datenkategorien</h3>
                  <p>Verarbeitet werden Einsatzdaten, medizinische Gesundheitsdaten, Vitalwerte, Maßnahmen, Übergabeinformationen, Besatzung, technische Sitzungsdaten, Auditereignisse und Exportnachweise. Patientennamen und private Adressdaten bleiben im Pilotbetrieb bewusst deaktiviert bzw. werden serverseitig gefiltert.</p>
                </article>
                <article>
                  <h3>4. Rechtsgrundlagen</h3>
                  <p>Die konkrete Rechtsgrundlage ist vom Betreiber festzulegen. Relevante Prüfanker sind DSGVO Art. 5, Art. 6, Art. 9 fuer Gesundheitsdaten, Art. 25 Datenschutz durch Technikgestaltung und Art. 32 Sicherheit der Verarbeitung. Eine medizinisch-organisatorische Freigabe ist vor Wirkbetrieb erforderlich.</p>
                </article>
                <article>
                  <h3>5. Datenminimierung</h3>
                  <p>Es werden nur Daten erhoben, die fuer Dokumentation, Patientensicherheit, Übergabe, Nachvollziehbarkeit oder rechtliche Pflichten erforderlich sind. Kartenlinks erhalten nur Einsatzort oder Koordinaten, keine Patientendaten, Einsatznummern oder medizinischen Angaben.</p>
                </article>
                <article>
                  <h3>6. Zugriff und Rollen</h3>
                  <p>Der Zugriff erfolgt personenbezogen mit Passwort. Rollen trennen normale Mitarbeitende, Azubis, BuFDi/Praktikanten und Admins. Transportführerwechsel verlangt Passwort des neuen TF, damit die aktive Session und Verantwortlichkeit nachvollziehbar wechseln.</p>
                </article>
                <article>
                  <h3>7. Technische Maßnahmen</h3>
                  <p>Patienten- und Protokolldaten werden serverseitig verschlüsselt gespeichert. Passwörter werden gehasht, Sitzungen laufen zeitlich ab, Reauthentifizierung stellt die Schicht wieder her. HTTPS, Server-Hardening, Backups, Updates und Zugriffsschutz sind verpflichtende Betriebsmaßnahmen.</p>
                </article>
                <article>
                  <h3>8. Organisatorische Maßnahmen</h3>
                  <p>Benutzer werden nur durch berechtigte Admins angelegt. Konten ausscheidender Personen sind zu deaktivieren. Exporte und Ausdrucke duerfen nur dienstlich genutzt werden. Schulung, Berechtigungskonzept, Meldewege und Verantwortlichkeiten muessen dokumentiert sein.</p>
                </article>
                <article>
                  <h3>9. Schnittstellen</h3>
                  <p>Leitstellenimporte sollen nur Einsatznummer, Stichwort, Straße, Hausnummer, Ort und Koordinaten enthalten. Eingehende Einsätze werden zuerst als wartender Einsatz angezeigt und erst nach bewusster Übernahme in den Entwurf geschrieben.</p>
                </article>
                <article>
                  <h3>10. Protokollierung</h3>
                  <p>Anmeldung, Reauthentifizierung, Import, Export, Druck, Fallabschluss und administrative Aktionen werden auditierbar protokolliert. Auditdaten enthalten notwendige Metadaten und sind vor unberechtigtem Zugriff zu schützen.</p>
                </article>
                <article>
                  <h3>11. Aufbewahrung und Löschung</h3>
                  <p>Aufbewahrungsfristen werden durch den Betreiber nach gesetzlichen und organisatorischen Vorgaben festgelegt. NANA unterstützt Retention-Einstellungen, Anonymisierung, Löschmarkierung und Bereinigung abgelaufener Fälle.</p>
                </article>
                <article>
                  <h3>12. Betroffenenrechte</h3>
                  <p>Auskunft, Berichtigung, Löschung, Einschränkung und Nachvollziehbarkeit muessen über Betreiberprozesse abgebildet werden. Medizinische Dokumentationspflichten und gesetzliche Aufbewahrung koennen Löschung im Einzelfall begrenzen.</p>
                </article>
                <article>
                  <h3>13. Datenschutz-Folgenabschätzung</h3>
                  <p>Wegen Gesundheitsdaten, Einsatzkontext und mobiler Nutzung ist vor produktivem Betrieb eine DSFA zu prüfen und voraussichtlich durchzuführen. Risiken: Fehlzugriff, Geräteverlust, falscher Export, externe Kartendienste, unklare Schnittstelleninhalte.</p>
                </article>
                <article>
                  <h3>14. Freigabepunkte</h3>
                  <p>Vor Echtbetrieb offen: Betreiber festlegen, AV-Verträge prüfen, TOMs abnehmen, Löschfristen bestätigen, Leitstellen-Schnittstelle vertraglich beschreiben, Kartenanbieter bewerten, Notfall-/Backupkonzept testen und Datenschutzinformation erstellen.</p>
                </article>
              </div>
            </div>
          )}

          {activePanel === 'feedback' && (
            <div className="user-feedback-panel">
              <form className="feedback-form" onSubmit={submitFeedback}>
                <select value={feedbackDraft.kind} onChange={(event) => setFeedbackDraft({ ...feedbackDraft, kind: event.target.value })}>
                  <option value="Bug">Bug</option>
                  <option value="Wunsch">Wunsch</option>
                </select>
                <input value={feedbackDraft.title} onChange={(event) => setFeedbackDraft({ ...feedbackDraft, title: event.target.value })} placeholder="Kurzbeschreibung" />
                <textarea value={feedbackDraft.message} onChange={(event) => setFeedbackDraft({ ...feedbackDraft, message: event.target.value })} rows={4} placeholder="Was ist passiert oder was wünschst du dir?" />
                <button type="submit">Absenden</button>
              </form>
              <div className="user-dropdown-list">
                {(announcements.feedback || []).length === 0 ? (
                  <p className="muted">Noch keine eigenen Meldungen.</p>
                ) : announcements.feedback.map((item) => (
                  <article className="dropdown-entry" key={item.id}>
                    <strong>{item.kind}: {item.title}</strong>
                    <span>{item.created_at}</span>
                    <span className={feedbackStatusClass(item.status)}>{feedbackStatusLabel(item.status)}</span>
                    <p>{item.message}</p>
                    {item.answer && <p><b>Antwort:</b> {item.answer}</p>}
                  </article>
                ))}
              </div>
            </div>
          )}
          <div className="user-dropdown-footer">
            <span>Angemeldet als {employee?.name || 'Benutzer'}</span>
            <button type="button" className="dropdown-logout" onClick={onLogout}><LogOut size={16} /> Abmelden</button>
          </div>
        </div>
      )}
    </div>
  );
}

const tileIcons = {
  protocol: FileText,
  refusal: ShieldCheck,
  cancelled: AlertTriangle,
  approach: MapPinned,
  hospital: Building2,
  icd10: Stethoscope,
  devices: Wrench,
  interfaces: Cable,
  admin: ShieldCheck
};

function parseCoordinates(value) {
  const match = String(value || '').trim().match(/^(-?\d+(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d+(?:[.,]\d+)?)$/);
  if (!match) return null;
  const lat = Number(match[1].replace(',', '.'));
  const lng = Number(match[2].replace(',', '.'));
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return null;
  return { lat, lng };
}

function approachLinks(locationText) {
  const trimmed = String(locationText || '').trim();
  const coords = parseCoordinates(trimmed);
  const query = coords ? `${coords.lat},${coords.lng}` : trimmed;
  const encoded = encodeURIComponent(query);
  const overpassQuery = coords
    ? `[out:json][timeout:20];way(around:35,${coords.lat},${coords.lng})[highway];out tags geom;`
    : '';
  return {
    query,
    coords,
    apple: `https://maps.apple.com/?q=${encoded}`,
    google: `https://www.google.com/maps/search/?api=1&query=${encoded}`,
    streetView: coords
      ? `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${coords.lat},${coords.lng}`
      : `https://www.google.com/maps/search/?api=1&query=${encoded}`,
    osm: coords
      ? `https://www.openstreetmap.org/?mlat=${coords.lat}&mlon=${coords.lng}#map=18/${coords.lat}/${coords.lng}`
      : `https://www.openstreetmap.org/search?query=${encoded}`,
    maxspeed: coords
      ? `https://overpass-turbo.eu/?Q=${encodeURIComponent(overpassQuery)}`
      : `https://www.openstreetmap.org/search?query=${encoded}`
  };
}

function approachLocationFromDraft(patient) {
  const approach = patient?.anfahrt || {};
  const dispatch = patient?.einsatz || {};
  const coordinates = approach.coordinates || dispatch.koordinaten || '';
  if (coordinates) return String(coordinates);
  const address = approach.address || dispatch.adresse || '';
  if (address) return String(address);
  const streetLine = [approach.street || dispatch.strasse, approach.house_number || dispatch.hausnummer]
    .filter(hasValue)
    .join(' ');
  return [streetLine, approach.town || dispatch.ort].filter(hasValue).join(', ');
}

function approachSummaryFromDraft(patient) {
  const approach = patient?.anfahrt || {};
  const dispatch = patient?.einsatz || {};
  return {
    source: approach.source || (dispatch.adresse || dispatch.koordinaten ? 'dispatch' : ''),
    address: approach.address || dispatch.adresse || '',
    street: approach.street || dispatch.strasse || '',
    houseNumber: approach.house_number || dispatch.hausnummer || '',
    town: approach.town || dispatch.ort || '',
    coordinates: approach.coordinates || dispatch.koordinaten || ''
  };
}

const cancellationReasons = [
  'Nur Tragehilfe / technische Hilfeleistung',
  'Einsatz durch Leitstelle abgebrochen',
  'Einsatz aus Wettergründen nicht durchführbar',
  'Ausfall der Besatzung',
  'Technischer Fehler am Fahrzeug',
  'Fahrzeug nicht einsatzbereit',
  'Einsatzort nicht erreichbar',
  'Patient/in nicht auffindbar',
  'Kein Patient / Fehleinsatz',
  'Doppelalarmierung',
  'Versorgung durch anderes Rettungsmittel übernommen',
  'Polizei / Feuerwehr übernimmt',
  'Sonstiges'
];
const cancellationDispatcherSnippets = [
  'Leitstelle über Funk informiert',
  'Leitstelle telefonisch informiert',
  'Rücksprache mit Einsatzleitung erfolgt',
  'Rückmeldung an Wache / Dienstführung',
  'Dokumentation nachträglich ergänzt'
];
const cancellationAlternativeSnippets = [
  'Ersatzrettungsmittel alarmiert',
  'Versorgung durch anderes Rettungsmittel übernommen',
  'Technik / Werkstatt informiert',
  'Führungskraft informiert',
  'Kein weiterer Handlungsbedarf'
];
const cancellationDetailSnippets = [
  'Einsatz vor Eintreffen abgebrochen.',
  'Anfahrt nicht möglich bzw. nicht vertretbar.',
  'Rettungsmittel war aus technischen Gründen nicht einsatzbereit.',
  'Patient/in wurde nicht angetroffen.',
  'Lage wurde durch andere Einheit übernommen.'
];

function Login({ onLogin }) {
  const [employees, setEmployees] = useState([]);
  const [employeeId, setEmployeeId] = useState('');
  const [employeeQuery, setEmployeeQuery] = useState('');
  const [employeePickerOpen, setEmployeePickerOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [adminName, setAdminName] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [pendingChange, setPendingChange] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/auth/employees')
      .then((data) => {
        setEmployees(data.employees || []);
        const firstEmployee = data.employees?.[0];
        setEmployeeId(firstEmployee?.id || '');
        setEmployeeQuery(firstEmployee ? `${firstEmployee.name} · ${qualificationLabel(firstEmployee.qualification)}` : '');
      })
      .catch((err) => setError(err.message));
  }, []);
  const selectedEmployee = employees.find((employee) => employee.id === employeeId);
  const employeeQueryValue = employeeQuery.trim().toLowerCase();
  const filteredLoginEmployees = employeeQueryValue
    ? employees.filter((employee) => [
        employee.name,
        employee.qualification,
        roleLabel(employee.role),
        employee.station,
        employee.vehicle_scope
      ].join(' ').toLowerCase().includes(employeeQueryValue))
    : employees;

  function selectLoginEmployee(employee) {
    setEmployeeId(employee.id);
    setEmployeeQuery(`${employee.name} · ${qualificationLabel(employee.qualification)}`);
    setEmployeePickerOpen(false);
  }

  function handleEmployeeSearchKey(event) {
    if (event.key !== 'Enter') return;
    const nextEmployee = filteredLoginEmployees[0];
    if (!nextEmployee) return;
    event.preventDefault();
    selectLoginEmployee(nextEmployee);
  }

  async function submitLogin(event) {
    event.preventDefault();
    setError('');
    try {
      const result = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ employee_id: employeeId, password, ...browserDeviceInfo() })
      });
      if (result.status === 'password_change_required') {
        setPendingChange(result);
        return;
      }
      onLogin(result);
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitFirstAdmin(event) {
    event.preventDefault();
    setError('');
    try {
      const result = await api('/api/auth/setup-first-admin', {
        method: 'POST',
        body: JSON.stringify({ name: adminName, password: adminPassword, ...browserDeviceInfo() })
      });
      onLogin(result);
    } catch (err) {
      setError(err.message);
    }
  }

  async function submitPasswordChange(event) {
    event.preventDefault();
    setError('');
    try {
      const result = await api('/api/auth/set-password', {
        method: 'POST',
        body: JSON.stringify({ token: pendingChange.token, new_password: newPassword, ...browserDeviceInfo() })
      });
      onLogin(result);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="login-shell">
      <section className="brand-panel">
        <div className="brand-mark">
          <span>NANA</span>
        </div>
        <p>Notfall-Aufzeichnungs- und Nachbearbeitungs-Assistent</p>
      </section>

      <section className="login-panel">
        <div className="panel-title">
          <Lock size={22} />
          <h1>{pendingChange ? 'Passwort setzen' : 'Mitarbeiter-Login'}</h1>
        </div>

        {pendingChange ? (
          <form onSubmit={submitPasswordChange}>
            <label>
              Neues Passwort
              <input
                type="password"
                value={newPassword}
                minLength={12}
                onChange={(event) => setNewPassword(event.target.value)}
                autoFocus
              />
            </label>
            <button type="submit">Passwort speichern</button>
          </form>
        ) : employees.length === 0 ? (
          <form onSubmit={submitFirstAdmin}>
            <label>
              Ersten Admin anlegen
              <input
                type="text"
                value={adminName}
                onChange={(event) => setAdminName(event.target.value)}
                placeholder="Name"
                autoFocus
              />
            </label>
            <label>
              Admin-Passwort
              <input
                type="password"
                value={adminPassword}
                minLength={12}
                onChange={(event) => setAdminPassword(event.target.value)}
              />
            </label>
            <button type="submit">Admin erstellen</button>
          </form>
        ) : (
          <form onSubmit={submitLogin}>
            <label>
              Mitarbeiter
              <div className="login-employee-picker">
                <button
                  type="button"
                  className={`login-employee-toggle ${employeePickerOpen ? 'active' : ''}`}
                  onClick={() => {
                    setEmployeePickerOpen((current) => !current);
                    setEmployeeQuery('');
                  }}
                  aria-expanded={employeePickerOpen}
                >
                  <UserRound size={17} />
                  <span>
                    <strong>{selectedEmployee?.name || 'Mitarbeiter auswählen'}</strong>
                    <small>
                      {selectedEmployee
                        ? `${qualificationLabel(selectedEmployee.qualification)} · ${stationLabel(selectedEmployee.station)} · ${vehicleScopeLabel(selectedEmployee.vehicle_scope)}`
                        : 'Aufklappen und Namen suchen'}
                    </small>
                  </span>
                  <ChevronDown size={18} />
                </button>
                {employeePickerOpen && (
                  <div className="login-employee-popover">
                    <div className="login-employee-search">
                      <Search size={17} />
                      <input
                        type="search"
                        value={employeeQuery}
                        onChange={(event) => {
                          setEmployeeQuery(event.target.value);
                        }}
                        onKeyDown={handleEmployeeSearchKey}
                        placeholder="Name suchen"
                        autoComplete="off"
                        autoFocus
                      />
                    </div>
                    <div className="login-employee-results">
                      {filteredLoginEmployees.slice(0, 8).map((employee) => (
                        <button
                          type="button"
                          key={employee.id}
                          className={employee.id === employeeId ? 'active' : ''}
                          onClick={() => selectLoginEmployee(employee)}
                        >
                          <UserRound size={16} />
                          <span>
                            <strong>{employee.name}</strong>
                            <small>{qualificationLabel(employee.qualification)} · {stationLabel(employee.station)} · {vehicleScopeLabel(employee.vehicle_scope)}</small>
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </label>
            <label>
              Passwort
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <button type="submit" disabled={!employeeId}>Einloggen</button>
          </form>
        )}

        {error && <div className="error-box">{error}</div>}
      </section>
    </main>
  );
}

function ReauthLock({ lockedSession, onRestore, onSwitchUser }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const employee = lockedSession?.employee || {};

  async function submitReauth(event) {
    event.preventDefault();
    setError('');
    try {
      const result = await api('/api/auth/reauth', {
        method: 'POST',
        body: JSON.stringify({ employee_id: employee.id, password, restore_shift: true, ...browserDeviceInfo() })
      });
      onRestore(result);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="login-shell">
      <section className="brand-panel">
        <div className="brand-mark">
          <span>NANA</span>
        </div>
        <p>Schicht gesperrt. Der Entwurf bleibt erhalten und wird nach Passwortprüfung wieder geöffnet.</p>
      </section>

      <section className="login-panel reauth-panel">
        <div className="panel-title">
          <Lock size={22} />
          <h1>Schicht wiederherstellen</h1>
        </div>
        <div className="reauth-user">
          <span className="user-avatar">{(employee.name || 'P').trim().charAt(0).toUpperCase()}</span>
          <div>
            <strong>{employee.name || 'Mitarbeiter'}</strong>
            <span>{qualificationLabel(employee.qualification)}</span>
          </div>
        </div>
        <form onSubmit={submitReauth}>
          <label>
            Passwort
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoFocus
            />
          </label>
          <button type="submit">Schicht wiederherstellen</button>
        </form>
        <button type="button" className="secondary-login-action" onClick={onSwitchUser}>Benutzer wechseln</button>
        {error && <div className="error-box">{error}</div>}
      </section>
    </main>
  );
}

function LoginTransition({ session, onComplete }) {
  useEffect(() => {
    const timer = window.setTimeout(onComplete, 4200);
    return () => window.clearTimeout(timer);
  }, [onComplete]);

  return (
    <main className="login-transition-shell" aria-live="polite">
      <div className="ambulance-scene">
        <div className="letter-shower" aria-hidden="true">
          {['N', 'A', 'N', 'Ü', 'N', 'A', 'N', 'A'].map((letter, index) => (
            <span key={`${letter}-${index}`} style={{ '--letter-delay': `${0.2 + index * 0.1}s`, '--fall-x': `${(index - 3.5) * 18}px` }}>
              {letter}
            </span>
          ))}
        </div>
        <div className="ambulance-wrap" aria-hidden="true">
          <div className="ambulance">
            <svg className="ambulance-svg" viewBox="0 0 520 230" role="img" aria-label="Rettungswagen">
              <defs>
                <linearGradient id="rtwBody" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ffffff" />
                  <stop offset="72%" stopColor="#edf5fb" />
                  <stop offset="100%" stopColor="#d9e5ee" />
                </linearGradient>
                <linearGradient id="rtwGlass" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#dff5ff" />
                  <stop offset="100%" stopColor="#72b8ff" />
                </linearGradient>
                <filter id="rtwShadow" x="-20%" y="-20%" width="140%" height="150%">
                  <feDropShadow dx="0" dy="18" stdDeviation="12" floodColor="#000814" floodOpacity="0.42" />
                </filter>
              </defs>
              <ellipse cx="268" cy="197" rx="212" ry="20" fill="rgba(0,0,0,0.26)" />
              <g filter="url(#rtwShadow)">
                <path d="M179 66 H414 C439 66 458 85 458 110 V161 H165 V84 C165 74 169 66 179 66 Z" fill="url(#rtwBody)" stroke="#c9d6e2" strokeWidth="4" />
                <path d="M70 111 C81 87 106 72 136 72 H184 V161 H52 V140 C52 127 59 116 70 111 Z" fill="url(#rtwBody)" stroke="#c9d6e2" strokeWidth="4" />
                <path d="M76 113 C88 91 108 83 136 83 H162 V119 H66 C68 117 72 114 76 113 Z" fill="url(#rtwGlass)" stroke="#5f748b" strokeWidth="3" />
                <path d="M169 83 H183 V124 H151 Z" fill="#cfeeff" stroke="#5f748b" strokeWidth="3" />
                <path d="M205 84 H267 V119 H205 Z" fill="url(#rtwGlass)" stroke="#5f748b" strokeWidth="3" />
                <path d="M284 84 H346 V119 H284 Z" fill="url(#rtwGlass)" stroke="#5f748b" strokeWidth="3" />
                <path d="M363 84 H423 V119 H363 Z" fill="url(#rtwGlass)" stroke="#5f748b" strokeWidth="3" />
                <path d="M53 135 H459 V154 H53 Z" fill="#e51f3f" />
                <path d="M92 135 L130 135 L108 154 H70 Z" fill="#ffffff" opacity="0.88" />
                <path d="M184 67 V161" stroke="#c9d6e2" strokeWidth="3" />
                <path d="M224 129 H272 V176 H224 Z" fill="#f7fbff" stroke="#c9d6e2" strokeWidth="3" />
                <path d="M252 133 V172" stroke="#d5e0eb" strokeWidth="2" />
                <path d="M382 94 H430 V145 H382 Z" fill="#f7fbff" stroke="#c9d6e2" strokeWidth="3" />
                <path d="M406 103 V136 M390 119 H422" stroke="#e51f3f" strokeWidth="10" strokeLinecap="round" />
                <path d="M71 143 H121" stroke="#18283b" strokeWidth="5" strokeLinecap="round" />
                <path d="M69 153 H116" stroke="#18283b" strokeWidth="5" strokeLinecap="round" />
                <path d="M137 125 L153 121 L154 133 L137 137 Z" fill="#20344c" opacity="0.75" />
                <text x="293" y="151" fill="#19314d" fontSize="34" fontWeight="900" letterSpacing="3">RTW</text>
                <path d="M46 150 H86 V169 H47 C42 169 38 164 40 158 L42 154 C43 151 45 150 46 150 Z" fill="#1f2d3d" />
                <path d="M445 150 H468 C474 150 478 155 478 161 V169 H445 Z" fill="#1f2d3d" />
                <g className="ambulance-svg-wheel">
                  <circle cx="119" cy="166" r="31" fill="#07111f" />
                  <circle cx="119" cy="166" r="18" fill="#32475d" />
                  <path d="M119 148 V184 M101 166 H137 M106 153 L132 179 M132 153 L106 179" stroke="#dfeaf4" strokeWidth="3" strokeLinecap="round" />
                  <circle cx="119" cy="166" r="6" fill="#f6fbff" />
                </g>
                <g className="ambulance-svg-wheel">
                  <circle cx="386" cy="166" r="31" fill="#07111f" />
                  <circle cx="386" cy="166" r="18" fill="#32475d" />
                  <path d="M386 148 V184 M368 166 H404 M373 153 L399 179 M399 153 L373 179" stroke="#dfeaf4" strokeWidth="3" strokeLinecap="round" />
                  <circle cx="386" cy="166" r="6" fill="#f6fbff" />
                </g>
                <circle cx="57" cy="130" r="8" fill="#fff0a3" className="ambulance-headbeam" />
                <rect x="455" y="123" width="12" height="24" rx="5" fill="#ff3c5d" />
                <rect x="224" y="52" width="36" height="17" rx="7" fill="#2d7cff" className="ambulance-svg-light ambulance-svg-blue" />
                <rect x="268" y="52" width="36" height="17" rx="7" fill="#ff3c5d" className="ambulance-svg-light ambulance-svg-red" />
              </g>
            </svg>
          </div>
        </div>
        <div className="final-logo-lockup">
          <div className="final-nana" aria-label="NANA">
            {['N', 'A', 'N', 'A'].map((letter, index) => <span key={index}>{letter}</span>)}
          </div>
          <p>Notfall-Aufzeichnungs- und Nachbearbeitungs-Assistent</p>
        </div>
      </div>
    </main>
  );
}

function ApproachView({ session, employee, onBack, onLogout }) {
  const [location, setLocation] = useState('');
  const [notes, setNotes] = useState('');
  const [draftSource, setDraftSource] = useState(null);
  const [externalMapsEnabled, setExternalMapsEnabled] = useState(false);
  const [error, setError] = useState('');
  const links = approachLinks(location);
  const hasLocation = Boolean(location.trim());
  const linksEnabled = hasLocation && externalMapsEnabled;
  const linkClass = linksEnabled ? 'approach-link' : 'approach-link disabled';

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api('/api/draft', {}, session.token),
      api('/api/privacy/settings', {}, session.token).catch(() => ({ external_maps_enabled: false }))
    ])
      .then(([data, settings]) => {
        if (cancelled) return;
        setExternalMapsEnabled(Boolean(settings.external_maps_enabled));
        const nextLocation = approachLocationFromDraft(data.patient);
        const summary = approachSummaryFromDraft(data.patient);
        if (nextLocation && !location) setLocation(nextLocation);
        if (summary.source) setDraftSource(summary);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [session.token]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Anfahrt & Lage</div>
        </div>
        <div className="user-area">
          <button className="header-button" type="button" onClick={onBack}>
            <Home size={16} /> Hauptmenü
          </button>
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {error && <div className="error-box">{error}</div>}

      <section className="work-panel approach-panel">
        <div className="section-head">
          <h2>Anfahrt & Lage</h2>
          <span>{employee?.name || 'Einsatzteam'}</span>
        </div>
        <div className="approach-layout">
          <div className="approach-form">
            <label>
              Einsatzort oder Koordinaten
              <input
                value={location}
                onChange={(event) => setLocation(event.target.value)}
                placeholder="Adresse oder 51.8431, 6.8579"
              />
            </label>
            <label>
              Lagehinweise
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                rows={5}
                placeholder="z.B. VU Kreuzung, Anfahrt über Nebenstraße, RTW-Aufstellung prüfen"
              />
            </label>
            <div className="approach-quick-row">
              <button type="button" onClick={() => setLocation('Borken, Nordrhein-Westfalen')}>
                Borken
              </button>
              <button type="button" onClick={() => setNotes('RTW-Aufstellung, Eigenschutz, Verkehrsfluss und Rettungsweg vor Ort prüfen.')}>
                Lagehinweis
              </button>
            </div>
          </div>
          <div className="approach-card">
            <MapPinned size={34} />
            <strong>{hasLocation ? links.query : 'Kein Einsatzort gesetzt'}</strong>
            <span>{links.coords ? `Koordinaten erkannt: ${links.coords.lat}, ${links.coords.lng}` : 'Bei Koordinaten kann Street View direkter geöffnet werden.'}</span>
            {draftSource && (
              <div className="approach-source">
                <b>Aus Leitstelle übernommen</b>
                <span>{[draftSource.street && `${draftSource.street} ${draftSource.houseNumber || ''}`.trim(), draftSource.town].filter(Boolean).join(', ') || draftSource.address || draftSource.coordinates}</span>
              </div>
            )}
            {notes && <p>{notes}</p>}
          </div>
        </div>
        <div className="approach-actions">
          <a className={linkClass} href={linksEnabled ? links.apple : undefined} target="_blank" rel="noreferrer">
            Apple Karten
          </a>
          <a className={linkClass} href={linksEnabled ? links.google : undefined} target="_blank" rel="noreferrer">
            Google Maps
          </a>
          <a className={linkClass} href={linksEnabled ? links.streetView : undefined} target="_blank" rel="noreferrer">
            Street View
          </a>
          <a className={linkClass} href={linksEnabled ? links.osm : undefined} target="_blank" rel="noreferrer">
            OpenStreetMap
          </a>
          <a className={linkClass} href={linksEnabled ? links.maxspeed : undefined} target="_blank" rel="noreferrer">
            Tempolimit prüfen
          </a>
        </div>
        {!externalMapsEnabled && (
          <div className="notice-box">
            Externe Kartendienste sind durch den Admin deaktiviert. Dadurch werden keine Einsatzorte an Apple, Google, OpenStreetMap oder Overpass übertragen.
          </div>
        )}
        <div className="notice-box">
          Beim Öffnen eines externen Kartendienstes wird nur der Einsatzort bzw. die Koordinate übergeben. Keine Patientendaten, Einsatznummern oder medizinischen Angaben mitsenden.
        </div>
        <div className="notice-box">
          Orientierungshilfe. Aktuelle Beschilderung, Lage, Weisungen und Eigenschutz vor Ort haben Vorrang. Keine Patientendaten an externe Kartendienste übermitteln.
        </div>
      </section>
    </main>
  );
}

function Dashboard({ session, onLogout, onSessionReplace, connectivity, onSync, installPromptAvailable, onInstallApp }) {
  const [dashboard, setDashboard] = useState(null);
  const [cases, setCases] = useState([]);
  const [view, setView] = useState(() => getInitialDashboardView());
  const [error, setError] = useState('');
  const [statusText, setStatusText] = useState('');
  const [pendingDispatch, setPendingDispatch] = useState(null);

  useEffect(() => {
    setDashboard(null);
    api('/api/dashboard', {}, session.token)
      .then(setDashboard)
      .catch((err) => setError(err.message));
    api('/api/cases', {}, session.token)
      .then((data) => setCases(data.cases || []))
      .catch(() => setCases([]));
  }, [session.token]);

  useEffect(() => {
    let cancelled = false;
    async function refreshPendingDispatch() {
      try {
        const data = await api('/api/dispatch/pending', {}, session.token);
        if (!cancelled) setPendingDispatch(data.pending || null);
      } catch {
        if (!cancelled) setPendingDispatch(null);
      }
    }
    refreshPendingDispatch();
    const interval = window.setInterval(refreshPendingDispatch, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [session.token]);

  const employee = dashboard?.employee || session.employee;
  const tiles = dashboard?.tiles || [];
  const activeCases = useMemo(() => cases.filter((item) => item.status !== 'deleted'), [cases]);

  async function logout() {
    await api('/api/auth/logout', { method: 'POST' }, session.token).catch(() => {});
    onLogout();
  }

  async function downloadCasePdf(caseId) {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest(`/api/cases/${caseId}/pdf`, {}, session.token);
      downloadBlob(file.blob, file.filename);
      setStatusText('PDF wurde erstellt.');
    } catch (err) {
      setError(err.message);
    }
  }

  async function printCasePdf(caseId) {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest(`/api/cases/${caseId}/pdf`, {}, session.token);
      await api('/api/protocol/print-audit', {
        method: 'POST',
        body: JSON.stringify({ case_id: caseId, source: 'archive' })
      }, session.token).catch(() => {});
      printBlob(file.blob);
      setStatusText('Druckfenster wurde geöffnet.');
    } catch (err) {
      setError(err.message);
    }
  }

  async function acceptPendingDispatch() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/dispatch/pending/accept', { method: 'POST' }, session.token);
      setPendingDispatch(null);
      setStatusText(`Einsatz übernommen: ${result.updated_at}`);
      setView('protocol');
    } catch (err) {
      setError(err.message);
    }
  }

  async function dismissPendingDispatch() {
    setError('');
    setStatusText('');
    try {
      await api('/api/dispatch/pending', { method: 'DELETE' }, session.token);
      setPendingDispatch(null);
      setStatusText('Leitstellen-Einsatz ausgeblendet.');
    } catch (err) {
      setError(err.message);
    }
  }

  if (view === 'protocol') {
    return <ProtocolView session={session} employee={employee} onSessionReplace={onSessionReplace} onBack={() => setView('home')} onLogout={logout} connectivity={connectivity} onSync={onSync} />;
  }

  if (view === 'refusal') {
    return <ProtocolView session={session} employee={employee} onSessionReplace={onSessionReplace} onBack={() => setView('home')} onLogout={logout} connectivity={connectivity} onSync={onSync} initialSection="verweigerung" standaloneRefusal />;
  }

  if (view === 'cancelled') {
    return <CancellationView session={session} employee={employee} onBack={() => setView('home')} onLogout={logout} connectivity={connectivity} />;
  }

  if (view === 'approach') {
    return <ApproachView session={session} employee={employee} onBack={() => setView('home')} onLogout={logout} />;
  }

  if (view === 'hospital') {
    return <HospitalView session={session} employee={employee} onBack={() => setView('home')} onOpenProtocol={() => setView('protocol')} onLogout={logout} />;
  }

  if (view === 'icd10') {
    return <Icd10View session={session} employee={employee} onBack={() => setView('home')} onOpenProtocol={() => setView('protocol')} onLogout={logout} />;
  }

  if (view === 'devices') {
    return <DevicesView session={session} employee={employee} onBack={() => setView('home')} onLogout={logout} />;
  }

  if (view === 'interfaces') {
    return (
      <InterfacesView
        session={session}
        employee={employee}
        connectivity={connectivity}
        onBack={() => setView('home')}
        onOpenProtocol={() => setView('protocol')}
        onLogout={logout}
      />
    );
  }

  if (view === 'admin') {
    return <AdminView session={session} employee={employee} onBack={() => setView('home')} onLogout={logout} />;
  }

  return (
    <main className="app-shell">
      <SystemStatus {...connectivity} />
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Notfall-Aufzeichnungs- und Nachbearbeitungs-Assistent</div>
        </div>
        <div className="user-area">
          <UserMenu session={session} employee={employee} onLogout={logout} />
          {installPromptAvailable && (
            <button className="header-button install-button" type="button" onClick={onInstallApp}>
              <Download size={16} />
              App installieren
            </button>
          )}
          <button className="icon-button" onClick={logout} aria-label="Abmelden">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}

      <section className="status-band">
        <div>
          <ShieldCheck size={20} />
          <span>{employee?.role === 'admin' ? 'Admin-Profil' : `${roleLabel(employee?.role)}-Profil`}</span>
        </div>
        <div>
          <Activity size={20} />
          <span>{activeCases.length} archivierte Einsätze sichtbar</span>
        </div>
      </section>

      {pendingDispatch && (
        <section className="dispatch-alert">
          <div className="dispatch-alert-icon">
            <AlertTriangle size={30} />
          </div>
          <div className="dispatch-alert-content">
            <span className="dispatch-alert-kicker">Neuer Einsatz von der Leitstelle</span>
            <h2>{pendingDispatch.summary?.title || 'Neuer Leitstellen-Einsatz'}</h2>
            <div className="dispatch-alert-grid">
              {pendingDispatch.summary?.case_number && (
                <span><b>Einsatznummer</b>{pendingDispatch.summary.case_number}</span>
              )}
              {pendingDispatch.summary?.location && (
                <span><b>Ort</b>{pendingDispatch.summary.location}</span>
              )}
              {pendingDispatch.summary?.coordinates && (
                <span><b>Koordinaten</b>{pendingDispatch.summary.coordinates}</span>
              )}
              {pendingDispatch.summary?.alarm_time && (
                <span><b>Alarmzeit</b>{pendingDispatch.summary.alarm_time}</span>
              )}
              {pendingDispatch.summary?.vehicle && (
                <span><b>Fahrzeug</b>{pendingDispatch.summary.vehicle}</span>
              )}
              {pendingDispatch.summary?.dispatch_center && (
                <span><b>Leitstelle</b>{pendingDispatch.summary.dispatch_center}</span>
              )}
            </div>
          </div>
          <div className="dispatch-alert-actions">
            <button type="button" className="primary" onClick={acceptPendingDispatch}>
              <CheckCircle2 size={18} /> Einsatz übernehmen
            </button>
            <button type="button" onClick={dismissPendingDispatch}>
              Ausblenden
            </button>
          </div>
        </section>
      )}

      <section className="tile-grid">
        {tiles.map((tile) => {
          const Icon = tileIcons[tile.id] || FileText;
          return (
            <button
              className={`tile tile-${tile.id}`}
              key={tile.id}
              onClick={() => {
                if (tile.id === 'protocol') setView('protocol');
                if (tile.id === 'refusal') setView('refusal');
                if (tile.id === 'cancelled') setView('cancelled');
                if (tile.id === 'approach') setView('approach');
                if (tile.id === 'hospital') setView('hospital');
                if (tile.id === 'icd10') setView('icd10');
                if (tile.id === 'devices') setView('devices');
                if (tile.id === 'interfaces') setView('interfaces');
                if (tile.id === 'admin') setView('admin');
              }}
            >
              <Icon size={32} />
              <span>{tile.label}</span>
              <small>{tile.subtitle}</small>
            </button>
          );
        })}
      </section>

      <section className="work-panel">
        <div className="section-head">
          <h2>Archiv</h2>
          <span>{activeCases.length} Fälle</span>
        </div>
        <div className="case-list">
          {activeCases.length === 0 ? (
            <p className="muted">Noch keine abgeschlossenen Einsätze sichtbar.</p>
          ) : (
            activeCases.slice(0, 6).map((item) => (
              <article className="case-row archive-row" key={item.id}>
                <div>
                  <strong>{item.summary}</strong>
                  <span>{item.completed_at}</span>
                </div>
                <span className={`status-pill status-${item.status}`}>{item.status}</span>
                <button type="button" onClick={() => downloadCasePdf(item.id)}>
                  <Download size={16} /> PDF
                </button>
                <button type="button" onClick={() => printCasePdf(item.id)}>
                  <Printer size={16} /> Drucken
                </button>
              </article>
            ))
          )}
        </div>
      </section>
    </main>
  );
}

function InterfacesView({ session, employee, connectivity, onBack, onOpenProtocol, onLogout }) {
  const [cases, setCases] = useState([]);
  const [source, setSource] = useState('dispatch');
  const [payload, setPayload] = useState('');
  const [importResult, setImportResult] = useState(null);
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/cases', {}, session.token)
      .then((data) => setCases(data.cases || []))
      .catch((err) => setError(err.message));
  }, [session.token]);

  async function importPayload() {
    setError('');
    setStatusText('');
    setImportResult(null);
    try {
      const result = await api('/api/admin/interfaces/import', {
        method: 'POST',
        body: JSON.stringify({ source, payload })
      }, session.token);
      setImportResult(result);
      if (result.status === 'pending') {
        setStatusText(`Leitstellen-Einsatz wartet im Hauptmenü: ${Object.keys(result.imported || {}).length} Felder.`);
      } else {
        setStatusText(`Import übernommen: ${Object.keys(result.imported || {}).length} Felder.`);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function exportDraft(format) {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest(`/api/admin/interfaces/export/draft/${format}`, {}, session.token);
      downloadBlob(file.blob, file.filename);
      setStatusText(`Entwurf als ${format.toUpperCase()} exportiert.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function exportCase(caseId, format) {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest(`/api/admin/interfaces/export/cases/${caseId}/${format}`, {}, session.token);
      downloadBlob(file.blob, file.filename);
      setStatusText(`Einsatz als ${format.toUpperCase()} exportiert.`);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="app-shell">
      <SystemStatus {...connectivity} />
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Schnittstellen · Import und Export</div>
        </div>
        <div className="user-area">
          <UserMenu session={session} employee={employee} onLogout={onLogout} />
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <section className="protocol-toolbar">
        <button type="button" onClick={onBack}>Zurück zum Hauptmenü</button>
        <button type="button" onClick={onOpenProtocol}>Zur Dokumentation</button>
      </section>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}

      <section className="interface-grid">
        <article className="work-panel">
          <div className="section-head">
            <h2>Import</h2>
            <span>Admin-only</span>
          </div>
          <div className="interface-import">
            <label>
              Quelle
              <select value={source} onChange={(event) => setSource(event.target.value)}>
                <option value="dispatch">Leitstelle JSON/CSV/Text</option>
                <option value="corpuls">Corpuls/Monitor JSON</option>
              </select>
            </label>
            <label>
              Importdaten
              <textarea
                value={payload}
                onChange={(event) => setPayload(event.target.value)}
                placeholder={'einsatznummer: 12345\nstichwort: VU\nstrasse: Musterstrasse\nhausnummer: 1\nort: Borken\nkoordinaten: 51.8431, 6.8579'}
                rows={12}
              />
            </label>
            <button type="button" onClick={importPayload}>
              {source === 'dispatch' ? 'Als eingehenden Einsatz senden' : 'Import in Dokumentation übernehmen'}
            </button>
          </div>
          {importResult && (
            <div className="import-result">
              {Object.entries(importResult.imported || {}).map(([key, value]) => (
                <div key={key}>
                  <strong>{key}</strong>
                  <span>{String(value)}</span>
                </div>
              ))}
            </div>
          )}
        </article>

        <article className="work-panel">
          <div className="section-head">
            <h2>Entwurf exportieren</h2>
            <span>NANA / FHIR</span>
          </div>
          <div className="export-actions">
            <button type="button" onClick={() => exportDraft('nana')}>
              <Download size={16} /> NANA JSON
            </button>
            <button type="button" onClick={() => exportDraft('fhir')}>
              <Download size={16} /> FHIR Bundle
            </button>
          </div>
          <div className="privacy-list">
            <div>
              <strong>Leitstellen-Import</strong>
              <span>JSON, CSV oder Text mit Feldnamen wird in Einsatzdaten übernommen.</span>
            </div>
            <div>
              <strong>Corpuls-Vorbereitung</strong>
              <span>JSON-Vitaldaten werden in den Vitalwerte-Abschnitt übernommen.</span>
            </div>
            <div>
              <strong>Audit</strong>
              <span>Jeder Import und Export wird im Audit-Log gespeichert.</span>
            </div>
          </div>
        </article>
      </section>

      <section className="work-panel">
        <div className="section-head">
          <h2>Archiv exportieren</h2>
          <span>{cases.length} Einsätze</span>
        </div>
        <div className="case-list">
          {cases.length === 0 ? (
            <p className="muted">Keine exportierbaren Einsätze vorhanden.</p>
          ) : cases.slice(0, 12).map((item) => (
            <article className="case-row interface-case-row" key={item.id}>
              <div>
                <strong>{item.summary}</strong>
                <span>{item.completed_at} · {item.employee_name || 'anonym'}</span>
              </div>
              <span className={`status-pill status-${item.status}`}>{item.status}</span>
              <button type="button" onClick={() => exportCase(item.id, 'nana')}>
                <Download size={16} /> NANA
              </button>
              <button type="button" onClick={() => exportCase(item.id, 'fhir')}>
                <Download size={16} /> FHIR
              </button>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

function HospitalView({ session, employee, onBack, onOpenProtocol, onLogout }) {
  const [town, setTown] = useState('Borken');
  const [category, setCategory] = useState('Allgemeine Notaufnahme');
  const [data, setData] = useState({ towns: [], categories: [], hospitals: [] });
  const [patient, setPatient] = useState(emptyPatient);
  const [newHospital, setNewHospital] = useState({ name: '', country: 'DE', address: '', town: '', phone: '', categories: [] });
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');

  async function loadHospitals(nextTown = town, nextCategory = category) {
    setError('');
    try {
      const [hospitalData, draftData] = await Promise.all([
        api(`/api/hospitals?town=${encodeURIComponent(nextTown)}&category=${encodeURIComponent(nextCategory)}`, {}, session.token),
        api('/api/draft', {}, session.token)
      ]);
      setData(hospitalData);
      setPatient({ ...emptyPatient, ...(draftData.patient || {}) });
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadHospitals();
  }, [session.token]);

  async function selectHospital(hospital) {
    setError('');
    setStatusText('');
    const nextPatient = {
      ...patient,
      transport: {
        ...(patient.transport || {}),
        hospital_id: hospital.id,
        hospital_name: hospital.name,
        hospital_country: hospital.country,
        hospital_address: hospital.address,
        distance_km: hospital.distance_km,
        category,
        town
      },
      uebergabe: {
        ...(patient.uebergabe || {}),
        ziel: hospital.name
      }
    };
    try {
      await api('/api/draft', {
        method: 'PUT',
        body: JSON.stringify({ patient: nextPatient })
      }, session.token);
      setPatient(nextPatient);
      setStatusText(`${hospital.name} wurde in die Dokumentation übernommen.`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveHospital(event) {
    event.preventDefault();
    setError('');
    setStatusText('');
    try {
      await api('/api/admin/hospitals', {
        method: 'POST',
        body: JSON.stringify(newHospital)
      }, session.token);
      setNewHospital({ name: '', country: 'DE', address: '', town: '', phone: '', categories: [] });
      setStatusText('Klinik wurde gespeichert.');
      await loadHospitals();
    } catch (err) {
      setError(err.message);
    }
  }

  function toggleNewHospitalCategory(item) {
    setNewHospital((current) => {
      const categories = current.categories.includes(item)
        ? current.categories.filter((entry) => entry !== item)
        : [...current.categories, item];
      return { ...current, categories };
    });
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Krankenhaus Finder · Zielklinik wählen</div>
        </div>
        <div className="user-area">
          <UserMenu session={session} employee={employee} onLogout={onLogout} />
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden"><LogOut size={18} /></button>
        </div>
      </header>

      <section className="protocol-toolbar">
        <button type="button" onClick={onBack}>Zurück zum Hauptmenü</button>
        <button type="button" onClick={onOpenProtocol}>Zur Dokumentation</button>
      </section>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}

      <section className="finder-controls">
        <label>
          Standort
          <select value={town} onChange={(event) => { setTown(event.target.value); loadHospitals(event.target.value, category); }}>
            {(data.towns || []).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>
          Leitsymptom / Fachrichtung
          <select value={category} onChange={(event) => { setCategory(event.target.value); loadHospitals(town, event.target.value); }}>
            {(data.categories || []).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </section>

      <section className="hospital-grid">
        {(data.hospitals || []).map((hospital) => (
          <article className="hospital-card" key={hospital.id}>
            <div className="hospital-meta">
              <span>{hospital.country}</span>
              <span>{hospital.distance_km ?? '-'} km</span>
              <span>{hospital.estimated_minutes ?? '-'} min</span>
            </div>
            <h2>{hospital.name}</h2>
            <p>{hospital.address}</p>
            {hospital.phone && <p>{hospital.phone}</p>}
            <div className="tag-list">
              {(hospital.categories || []).slice(0, 5).map((item) => <span key={item}>{item}</span>)}
            </div>
            <button type="button" onClick={() => selectHospital(hospital)}>Als Ziel übernehmen</button>
          </article>
        ))}
      </section>

      {employee?.role === 'admin' && (
        <section className="work-panel">
          <div className="section-head">
            <h2>Klinik pflegen</h2>
            <span>Admin</span>
          </div>
          <form className="hospital-admin-form" onSubmit={saveHospital}>
            <input value={newHospital.name} onChange={(event) => setNewHospital({ ...newHospital, name: event.target.value })} placeholder="Klinikname" />
            <input value={newHospital.address} onChange={(event) => setNewHospital({ ...newHospital, address: event.target.value })} placeholder="Adresse" />
            <input value={newHospital.phone} onChange={(event) => setNewHospital({ ...newHospital, phone: event.target.value })} placeholder="Telefon" />
            <select value={newHospital.country} onChange={(event) => setNewHospital({ ...newHospital, country: event.target.value })}>
              <option value="DE">DE</option>
              <option value="NL">NL</option>
            </select>
            <div className="check-grid">
              {(data.categories || []).map((item) => (
                <label key={item}>
                  <input type="checkbox" checked={newHospital.categories.includes(item)} onChange={() => toggleNewHospitalCategory(item)} />
                  {item}
                </label>
              ))}
            </div>
            <button type="submit">Klinik speichern</button>
          </form>
        </section>
      )}
    </main>
  );
}

function Icd10View({ session, employee, onBack, onOpenProtocol, onLogout }) {
  const [result, setResult] = useState(null);
  const [catalogQuery, setCatalogQuery] = useState('');
  const [catalogResult, setCatalogResult] = useState({ entries: [], source: '', catalog_size: 0 });
  const [patient, setPatient] = useState(emptyPatient);
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/draft', {}, session.token)
      .then((data) => setPatient({ ...emptyPatient, ...(data.patient || {}) }))
      .catch((err) => setError(err.message));
  }, [session.token]);

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      try {
        const query = catalogQuery.trim();
        const data = await api('/api/icd10/search', {
          method: 'POST',
          body: JSON.stringify({ query, limit: 80 })
        }, session.token);
        setCatalogResult(data);
        const normalizedQuery = query.replace(/\s+/g, '').toUpperCase();
        const exactEntry = (data.entries || []).find((entry) => entry.code === normalizedQuery);
        if (exactEntry) {
          setResult({ ...exactEntry, matched_code: exactEntry.code, found: true, source: data.source });
        } else if (/^[A-Z]\d{2}(?:\.[0-9A-Z]{1,2})?-?$/.test(normalizedQuery)) {
          const lookupData = await api('/api/icd10/lookup', {
            method: 'POST',
            body: JSON.stringify({ code: normalizedQuery })
          }, session.token);
          setResult(lookupData);
        } else {
          setResult(null);
        }
      } catch (err) {
        setError(err.message);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [catalogQuery, session.token]);

  async function applyIcdEntry(entry) {
    if (!entry) return;
    const nextPatient = {
      ...patient,
      einweisung: {
        ...(patient.einweisung || {}),
        icd_code: entry.code,
        diagnose: entry.diagnosis,
        source_url: entry.source_url || ''
      }
    };
    try {
      await api('/api/draft', {
        method: 'PUT',
        body: JSON.stringify({ patient: nextPatient })
      }, session.token);
      setPatient(nextPatient);
      setStatusText('ICD10 wurde in die Dokumentation übernommen.');
    } catch (err) {
      setError(err.message);
    }
  }

  async function translateCatalogQuery() {
    const query = catalogQuery.trim();
    if (!query) {
      setResult(null);
      setStatusText('Bitte ICD10-Code oder Suchbegriff eingeben.');
      return;
    }
    setError('');
    setStatusText('');
    try {
      const normalizedQuery = query.replace(/\s+/g, '').toUpperCase();
      const [lookupData, searchData] = await Promise.all([
        api('/api/icd10/lookup', {
          method: 'POST',
          body: JSON.stringify({ code: normalizedQuery })
        }, session.token),
        api('/api/icd10/search', {
          method: 'POST',
          body: JSON.stringify({ query, limit: 80 })
        }, session.token)
      ]);
      setCatalogResult(searchData);
      const exactEntry = (searchData.entries || []).find((entry) => entry.code === normalizedQuery);
      const firstEntry = (searchData.entries || [])[0];
      const nextResult = lookupData.found
        ? lookupData
        : exactEntry
          ? { ...exactEntry, matched_code: exactEntry.code, found: true, source: searchData.source }
          : firstEntry
            ? { ...firstEntry, matched_code: firstEntry.code, found: true, source: searchData.source }
            : lookupData;
      setResult(nextResult);
      setStatusText(nextResult.found ? `ICD10 ${nextResult.matched_code || nextResult.code} wurde übersetzt.` : 'Kein passender ICD10-Eintrag gefunden.');
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">ICD10 Code · Dekodierer</div>
        </div>
        <div className="user-area">
          <UserMenu session={session} employee={employee} onLogout={onLogout} />
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden"><LogOut size={18} /></button>
        </div>
      </header>
      <section className="protocol-toolbar">
        <button type="button" onClick={onBack}>Zurück zum Hauptmenü</button>
        <button type="button" onClick={onOpenProtocol}>Zur Dokumentation</button>
      </section>
      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}
      <section className="work-panel icd-panel">
        <div className="section-head">
          <h2>ICD10 suchen</h2>
          <span>{catalogResult.source || 'ICD-10-GM-Katalog'}</span>
        </div>
        <div className="icd-catalog-meta">
          <strong>{catalogResult.catalog_size || 0}</strong>
          <span>hinterlegte ICD10-Einträge</span>
        </div>
        <div className="icd-search">
          <label className="icd-search-field">
            ICD10-Katalog durchsuchen
            <input
              value={catalogQuery}
              onChange={(event) => setCatalogQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  translateCatalogQuery();
                }
              }}
              placeholder="Code oder Diagnose, z.B. F45, J45, Asthma, Schlaganfall"
            />
          </label>
          <button type="button" onClick={translateCatalogQuery}>Übersetzen</button>
        </div>
        {result && catalogQuery.trim() && (
          <div className="icd-result">
            <strong>{result.code}</strong>
            <span>{result.diagnosis}</span>
            <small>{result.found ? `Treffer über ${result.matched_code || result.code}` : 'Bitte fachlich prüfen und ggf. manuell ergänzen.'}</small>
            {result.found && <button type="button" onClick={() => applyIcdEntry(result)}>In Dokumentation übernehmen</button>}
          </div>
        )}
        <div className="icd-results-list">
          {(catalogResult.entries || []).map((entry) => (
            <button type="button" key={`${entry.code}-${entry.diagnosis}`} onClick={() => applyIcdEntry(entry)}>
              <strong>{entry.code}</strong>
              <span>{entry.diagnosis}</span>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}

function DevicesView({ session, employee, onBack, onLogout }) {
  const [devices, setDevices] = useState([]);
  const [selectedName, setSelectedName] = useState('');
  const [selectedTopic, setSelectedTopic] = useState('');
  const [stepIndex, setStepIndex] = useState(0);
  const [query, setQuery] = useState('');
  const [checkedSteps, setCheckedSteps] = useState({});
  const [error, setError] = useState('');

  useEffect(() => {
    api('/api/devices', {}, session.token)
      .then((data) => {
        const nextDevices = data.devices || [];
        setDevices(nextDevices);
        setSelectedName(nextDevices[0]?.name || '');
        setSelectedTopic(Object.keys(nextDevices[0]?.topics || {})[0] || '');
      })
      .catch((err) => setError(err.message));
  }, [session.token]);

  const selectedDevice = devices.find((item) => item.name === selectedName) || {};
  const topicNames = Object.keys(selectedDevice.topics || {});
  const steps = selectedDevice.topics?.[selectedTopic] || [];
  const currentStep = steps[Math.min(stepIndex, Math.max(steps.length - 1, 0))] || '';
  const filteredDevices = devices.filter((device) => {
    const haystack = `${device.name} ${device.model_note} ${Object.keys(device.topics || {}).join(' ')}`.toLowerCase();
    return haystack.includes(query.trim().toLowerCase());
  });
  const topicActions = selectedDevice.topic_actions?.[selectedTopic];
  const checklistKey = `${selectedName}:${selectedTopic}`;
  const checkedForTopic = checkedSteps[checklistKey] || {};
  const completedSteps = steps.filter((_, index) => checkedForTopic[index]).length;

  function selectDevice(name) {
    const device = devices.find((item) => item.name === name) || {};
    const firstTopic = Object.keys(device.topics || {})[0] || '';
    setSelectedName(name);
    setSelectedTopic(firstTopic);
    setStepIndex(0);
  }

  function toggleDeviceStep(index) {
    setCheckedSteps((current) => ({
      ...current,
      [checklistKey]: {
        ...(current[checklistKey] || {}),
        [index]: !Boolean((current[checklistKey] || {})[index])
      }
    }));
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Geräte · Kurzreferenzen</div>
        </div>
        <div className="user-area">
          <UserMenu session={session} employee={employee} onLogout={onLogout} />
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden"><LogOut size={18} /></button>
        </div>
      </header>
      <section className="protocol-toolbar">
        <button type="button" onClick={onBack}>Zurück zum Hauptmenü</button>
      </section>
      {error && <div className="error-box">{error}</div>}
      <section className="device-layout">
        <aside className="work-panel device-list">
          <label className="device-search">
            Geräte suchen
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="z. B. corpuls, Absaugung, Beatmung" />
          </label>
          {filteredDevices.map((device) => (
            <button type="button" className={device.name === selectedName ? 'active' : ''} key={device.name} onClick={() => selectDevice(device.name)}>
              <span>{device.icon}</span>
              <div>
                <strong>{device.name}</strong>
                <small>{Object.keys(device.topics || {}).length} Kurzreferenzen</small>
              </div>
            </button>
          ))}
          {filteredDevices.length === 0 && <p className="muted">Kein Gerät gefunden.</p>}
        </aside>
        <section className="work-panel device-detail">
          <div className="section-head">
            <h2>{selectedDevice.icon} {selectedDevice.name}</h2>
            <span>{selectedDevice.source_label}</span>
          </div>
          <p className="muted">{selectedDevice.model_note}</p>
          <div className="device-meta-grid">
            <div>
              <strong>{topicNames.length}</strong>
              <span>Themen</span>
            </div>
            <div>
              <strong>{steps.length}</strong>
              <span>Schritte</span>
            </div>
            <div>
              <strong>{completedSteps}</strong>
              <span>abgehakt</span>
            </div>
          </div>
          <select value={selectedTopic} onChange={(event) => { setSelectedTopic(event.target.value); setStepIndex(0); }}>
            {topicNames.map((topic) => <option key={topic} value={topic}>{topic}</option>)}
          </select>
          {topicActions && (
            <a className="device-action-link" href={topicActions.url} target="_blank" rel="noreferrer">
              {topicActions.label || 'Herstellerlink öffnen'}
              <small>{topicActions.hint}</small>
            </a>
          )}
          <div className="device-step">
            <span>Schritt {steps.length ? stepIndex + 1 : 0} / {steps.length}</span>
            <p>{currentStep}</p>
            {steps.length > 0 && (
              <label className="checkbox-line device-check-current">
                <input type="checkbox" checked={Boolean(checkedForTopic[stepIndex])} onChange={() => toggleDeviceStep(stepIndex)} />
                Schritt erledigt
              </label>
            )}
          </div>
          <div className="device-step-actions">
            <button type="button" onClick={() => setStepIndex(Math.max(0, stepIndex - 1))} disabled={stepIndex === 0}>Zurück</button>
            <button type="button" onClick={() => setStepIndex(Math.min(steps.length - 1, stepIndex + 1))} disabled={stepIndex >= steps.length - 1}>Weiter</button>
          </div>
          <div className="device-checklist">
            {steps.map((step, index) => (
              <button
                type="button"
                className={index === stepIndex ? 'active' : ''}
                key={`${selectedTopic}-${index}`}
                onClick={() => setStepIndex(index)}
              >
                <input type="checkbox" checked={Boolean(checkedForTopic[index])} onChange={(event) => { event.stopPropagation(); toggleDeviceStep(index); }} />
                <span>{index + 1}. {step}</span>
              </button>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function AdminView({ session, employee, onBack, onLogout }) {
  const [employees, setEmployees] = useState([]);
  const [auditEvents, setAuditEvents] = useState([]);
  const [loginEvents, setLoginEvents] = useState([]);
  const [privacy, setPrivacy] = useState(null);
  const [qualityRules, setQualityRules] = useState([]);
  const [cases, setCases] = useState([]);
  const [announcementData, setAnnouncementData] = useState({ patch_notes: [], planned_updates: [], feedback: [] });
  const [releaseInfo, setReleaseInfo] = useState(null);
  const [patchDraft, setPatchDraft] = useState({ title: '', body: '', published_at: '' });
  const [plannedDraft, setPlannedDraft] = useState({ title: '', body: '', published_at: '' });
  const [feedbackAnswers, setFeedbackAnswers] = useState({});
  const [feedbackFilter, setFeedbackFilter] = useState('alle');
  const [newName, setNewName] = useState('');
  const [newRole, setNewRole] = useState('employee');
  const [newQualification, setNewQualification] = useState('');
  const [newStation, setNewStation] = useState('');
  const [newVehicleScope, setNewVehicleScope] = useState('');
  const [employeeSearch, setEmployeeSearch] = useState('');
  const [employeeStationFilter, setEmployeeStationFilter] = useState('all');
  const [employeeVehicleFilter, setEmployeeVehicleFilter] = useState('all');
  const [retentionDays, setRetentionDays] = useState(3650);
  const [securityLogRetentionDays, setSecurityLogRetentionDays] = useState(180);
  const [externalMapsEnabled, setExternalMapsEnabled] = useState(false);
  const [temporaryPassword, setTemporaryPassword] = useState('');
  const [statusText, setStatusText] = useState('');
  const [error, setError] = useState('');
  const exportEvents = auditEvents.filter((event) => event.action.includes('pdf') || event.action.includes('print'));
  const feedbackItems = announcementData.feedback || [];
  const feedbackCounts = FEEDBACK_STATUS_OPTIONS.reduce((counts, statusValue) => {
    counts[statusValue] = feedbackItems.filter((item) => (item.status || 'offen') === statusValue).length;
    return counts;
  }, {});
  const visibleFeedbackItems = feedbackFilter === 'alle'
    ? feedbackItems
    : feedbackItems.filter((item) => (item.status || 'offen') === feedbackFilter);
  const activeEmployeeCount = employees.filter((item) => item.active).length;
  const lockedEmployeeCount = employees.filter((item) => !item.active).length;
  const adminEmployeeCount = employees.filter((item) => item.role === 'admin').length;
  const employeeSearchValue = employeeSearch.trim().toLowerCase();
  const stationSummaries = EMPLOYEE_STATION_OPTIONS.filter((station) => station.value).map((station) => {
    const stationEmployees = employees.filter((item) => item.station === station.value);
    return {
      ...station,
      active: stationEmployees.filter((item) => item.active).length,
      locked: stationEmployees.filter((item) => !item.active).length,
      ktw: stationEmployees.filter((item) => ['KTW', 'KTW/RTW'].includes(item.vehicle_scope)).length,
      rtw: stationEmployees.filter((item) => ['RTW', 'KTW/RTW'].includes(item.vehicle_scope)).length
    };
  });
  const unassignedEmployeeCount = employees.filter((item) => !item.station).length;
  const visibleEmployees = employees.filter((item) => {
    const matchesSearch = !employeeSearchValue || [
        item.name,
        item.station,
        item.vehicle_scope,
        item.qualification,
        roleLabel(item.role)
      ].join(' ').toLowerCase().includes(employeeSearchValue);
    const matchesStation = employeeStationFilter === 'all' || item.station === employeeStationFilter;
    const matchesVehicle = employeeVehicleFilter === 'all'
      || item.vehicle_scope === employeeVehicleFilter
      || (employeeVehicleFilter !== '' && item.vehicle_scope === 'KTW/RTW' && ['KTW', 'RTW'].includes(employeeVehicleFilter));
    return matchesSearch && matchesStation && matchesVehicle;
  });
  const privacyWarningCount = (privacy?.checklist || []).filter((item) => item.status === 'warning').length;
  const privacyOkCount = (privacy?.checklist || []).filter((item) => item.status === 'ok').length;
  const openFeedbackCount = feedbackCounts.offen || 0;

  async function loadAdminData() {
    setError('');
    try {
      const [employeeData, auditData, loginData, privacyData, caseData, announcementAdminData, releaseData] = await Promise.all([
        api('/api/admin/employees', {}, session.token),
        api('/api/admin/audit', {}, session.token),
        api('/api/admin/login-events', {}, session.token),
        api('/api/admin/privacy', {}, session.token),
        api('/api/cases', {}, session.token),
        api('/api/admin/announcements', {}, session.token),
        api('/api/admin/release', {}, session.token).catch(() => null)
      ]);
      const qualityData = await api('/api/admin/quality-rules', {}, session.token).catch(() => ({ rules: [] }));
      setEmployees(employeeData.employees || []);
      setAuditEvents(auditData.events || []);
      setLoginEvents(loginData.events || []);
      setPrivacy(privacyData);
      setQualityRules(qualityData.rules || []);
      setRetentionDays(privacyData.retention_days || 3650);
      setSecurityLogRetentionDays(privacyData.security_log_retention_days || 180);
      setExternalMapsEnabled(Boolean(privacyData.external_maps_enabled));
      setCases(caseData.cases || []);
      setAnnouncementData(announcementAdminData);
      setReleaseInfo(releaseData);
      setFeedbackAnswers(Object.fromEntries((announcementAdminData.feedback || []).map((item) => [item.id, item.answer || ''])));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadAdminData();
  }, [session.token]);

  async function createEmployee(event) {
    event.preventDefault();
    setError('');
    setStatusText('');
    setTemporaryPassword('');
    try {
      const result = await api('/api/admin/employees', {
        method: 'POST',
        body: JSON.stringify({
          name: newName,
          role: newRole,
          qualification: newQualification,
          station: newStation,
          vehicle_scope: newVehicleScope
        })
      }, session.token);
      setTemporaryPassword(`${result.employee.name}: ${result.temporary_password}`);
      setStatusText('Mitarbeiterprofil wurde angelegt.');
      setNewName('');
      setNewQualification('');
      setNewStation('');
      setNewVehicleScope('');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function updateEmployee(item, changes) {
    setError('');
    setStatusText('');
    setTemporaryPassword('');
    try {
      const result = await api(`/api/admin/employees/${item.id}`, {
        method: 'PUT',
        body: JSON.stringify(changes)
      }, session.token);
      if (result.temporary_password) {
        setTemporaryPassword(`${result.employee.name}: ${result.temporary_password}`);
      }
      setStatusText('Mitarbeiterprofil wurde aktualisiert.');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteEmployee(item) {
    if (item.id === employee?.id) {
      setError('Eigenes Admin-Profil kann nicht gelöscht werden.');
      return;
    }
    if (!window.confirm(`${item.name} wirklich löschen? Der aktuelle Entwurf dieses Profils wird entfernt.`)) {
      return;
    }
    setError('');
    setStatusText('');
    setTemporaryPassword('');
    try {
      await api(`/api/admin/employees/${item.id}`, { method: 'DELETE' }, session.token);
      setStatusText('Mitarbeiterprofil wurde gelöscht.');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveRetention() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/admin/privacy', {
        method: 'PUT',
        body: JSON.stringify({
          retention_days: Number(retentionDays),
          security_log_retention_days: Number(securityLogRetentionDays),
          external_maps_enabled: externalMapsEnabled
        })
      }, session.token);
      setStatusText(`Aufbewahrung gesetzt: ${result.retention_days} Tage, Logs ${result.security_log_retention_days} Tage.`);
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function purgeExpiredCases() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/admin/privacy/purge-expired', { method: 'POST' }, session.token);
      setStatusText(`${result.count} abgelaufene Einsätze gelöscht.`);
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function purgeSecurityEvents() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/admin/privacy/purge-security-events', { method: 'POST' }, session.token);
      const deleted = result.deleted || {};
      setStatusText(`${(deleted.audit_log || 0) + (deleted.login_events || 0)} alte Sicherheitsereignisse gelöscht.`);
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function anonymizeCase(caseId) {
    setError('');
    setStatusText('');
    try {
      await api(`/api/admin/cases/${caseId}/anonymize`, { method: 'POST' }, session.token);
      setStatusText('Einsatz wurde anonymisiert.');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function deleteCase(caseId) {
    setError('');
    setStatusText('');
    try {
      await api(`/api/admin/cases/${caseId}`, { method: 'DELETE' }, session.token);
      setStatusText('Einsatz wurde gelöscht.');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  function addAnnouncement(kind) {
    const draft = kind === 'patch_notes' ? patchDraft : plannedDraft;
    if (!draft.title.trim() && !draft.body.trim()) return;
    const item = {
      title: draft.title.trim() || 'Ohne Titel',
      body: draft.body.trim(),
      published_at: draft.published_at.trim() || new Date().toLocaleString('de-DE')
    };
    setAnnouncementData((current) => ({
      ...current,
      [kind]: [item, ...(current[kind] || [])]
    }));
    if (kind === 'patch_notes') setPatchDraft({ title: '', body: '', published_at: '' });
    if (kind === 'planned_updates') setPlannedDraft({ title: '', body: '', published_at: '' });
  }

  function addDeployPatchNote() {
    const draft = releaseInfo?.patch_note;
    if (!draft) {
      setError('Keine Deploy-Informationen verfügbar.');
      return;
    }
    const exists = (announcementData.patch_notes || []).some((item) => item.title === draft.title);
    if (exists) {
      setPatchDraft(draft);
      setStatusText('Patch Note für dieses Deploy ist bereits in der Liste. Entwurf wurde in die Felder übernommen.');
      return;
    }
    setAnnouncementData((current) => ({
      ...current,
      patch_notes: [draft, ...(current.patch_notes || [])]
    }));
    setPatchDraft(draft);
    setStatusText('Patch Note aus aktuellem Deploy vorbereitet. Text bitte ergänzen und speichern.');
  }

  function removeAnnouncement(kind, index) {
    setAnnouncementData((current) => ({
      ...current,
      [kind]: (current[kind] || []).filter((_, itemIndex) => itemIndex !== index)
    }));
  }

  async function saveAnnouncements() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/admin/announcements', {
        method: 'PUT',
        body: JSON.stringify({
          patch_notes: announcementData.patch_notes || [],
          planned_updates: announcementData.planned_updates || []
        })
      }, session.token);
      setAnnouncementData((current) => ({ ...current, ...result }));
      setStatusText('Patch Notes und geplante Updates wurden gespeichert.');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function answerFeedback(item, statusValue = item.status || 'offen') {
    setError('');
    setStatusText('');
    try {
      await api(`/api/admin/feedback/${item.id}`, {
        method: 'PUT',
        body: JSON.stringify({ status: statusValue, answer: feedbackAnswers[item.id] || '' })
      }, session.token);
      setStatusText('Antwort wurde gespeichert.');
      await loadAdminData();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Admin · Datenschutz & Benutzerverwaltung</div>
        </div>
        <div className="user-area">
          <UserMenu session={session} employee={employee} onLogout={onLogout} />
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <section className="protocol-toolbar admin-toolbar">
        <button type="button" onClick={onBack}><ArrowLeft size={17} /> Hauptmenü</button>
        <button type="button" onClick={loadAdminData}><RotateCcw size={17} /> Aktualisieren</button>
      </section>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}
      {temporaryPassword && (
        <div className="secret-box">
          <strong>Einmalpasswort nur jetzt anzeigen:</strong>
          <code>{temporaryPassword}</code>
        </div>
      )}

      <section className="admin-overview">
        <div className="admin-metric metric-teal">
          <span>Aktive Profile</span>
          <strong>{activeEmployeeCount}</strong>
          <small>{employees.length} insgesamt</small>
        </div>
        <div className="admin-metric metric-blue">
          <span>Admins</span>
          <strong>{adminEmployeeCount}</strong>
          <small>rollenbasierter Zugriff</small>
        </div>
        <div className="admin-metric metric-green">
          <span>Datenschutz</span>
          <strong>{privacyOkCount}</strong>
          <small>{privacyWarningCount} Hinweise</small>
        </div>
        <div className="admin-metric metric-rose">
          <span>Fällige Löschung</span>
          <strong>{privacy?.expired_cases || 0}</strong>
          <small>{securityLogRetentionDays || 180} Tage Logs</small>
        </div>
      </section>

      <section className="admin-grid admin-primary-grid">
        <article className="work-panel admin-card employee-admin-card">
          <div className="section-head">
            <div>
              <h2>Mitarbeiter</h2>
              <p>Konten, Rollen und Einmalpasswörter</p>
            </div>
            <span>{employees.length} Profile</span>
          </div>
          <form className="inline-form employee-create-form" onSubmit={createEmployee}>
            <input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Name" />
            <select value={newQualification} onChange={(event) => setNewQualification(event.target.value)} aria-label="Qualifikation">
              {EMPLOYEE_QUALIFICATION_OPTIONS.map((qualification) => (
                <option key={qualification.value || 'none'} value={qualification.value}>{qualification.label}</option>
              ))}
            </select>
            <select value={newStation} onChange={(event) => setNewStation(event.target.value)} aria-label="Rettungswache">
              {EMPLOYEE_STATION_OPTIONS.map((station) => (
                <option key={station.value || 'none'} value={station.value}>{station.label}</option>
              ))}
            </select>
            <select value={newVehicleScope} onChange={(event) => setNewVehicleScope(event.target.value)} aria-label="Einsatzmittel">
              {EMPLOYEE_VEHICLE_OPTIONS.map((vehicle) => (
                <option key={vehicle.value || 'none'} value={vehicle.value}>{vehicle.label}</option>
              ))}
            </select>
            <select value={newRole} onChange={(event) => setNewRole(event.target.value)}>
              {EMPLOYEE_ROLE_OPTIONS.map((role) => (
                <option key={role.value} value={role.value}>{role.label}</option>
              ))}
            </select>
            <button type="submit"><UserPlus size={17} /> Anlegen</button>
          </form>
          <label className="employee-search-field">
            <Search size={17} />
            <input
              value={employeeSearch}
              onChange={(event) => setEmployeeSearch(event.target.value)}
              placeholder="Mitarbeiter, Wache, KTW oder RTW suchen"
            />
          </label>
          <div className="employee-filter-panel">
            <div className="employee-filter-row" aria-label="Rettungswache filtern">
              <button type="button" className={employeeStationFilter === 'all' ? 'active' : ''} onClick={() => setEmployeeStationFilter('all')}>
                Alle
              </button>
              {EMPLOYEE_STATION_OPTIONS.filter((station) => station.value).map((station) => (
                <button
                  type="button"
                  key={station.value}
                  className={employeeStationFilter === station.value ? 'active' : ''}
                  onClick={() => setEmployeeStationFilter(station.value)}
                >
                  {station.label}
                </button>
              ))}
            </div>
            <div className="employee-filter-row" aria-label="Einsatzmittel filtern">
              <button type="button" className={employeeVehicleFilter === 'all' ? 'active' : ''} onClick={() => setEmployeeVehicleFilter('all')}>
                Alle Mittel
              </button>
              {EMPLOYEE_VEHICLE_OPTIONS.filter((vehicle) => vehicle.value).map((vehicle) => (
                <button
                  type="button"
                  key={vehicle.value}
                  className={employeeVehicleFilter === vehicle.value ? 'active' : ''}
                  onClick={() => setEmployeeVehicleFilter(vehicle.value)}
                >
                  {vehicle.label}
                </button>
              ))}
            </div>
          </div>
          <div className="station-summary-grid">
            {stationSummaries.map((station) => (
              <button
                type="button"
                className={`station-summary-card ${employeeStationFilter === station.value ? 'active' : ''}`}
                key={station.value}
                onClick={() => setEmployeeStationFilter(station.value)}
              >
                <MapPinned size={17} />
                <span>
                  <strong>{station.label}</strong>
                  <small>{station.active} aktiv · {station.locked} gesperrt</small>
                </span>
                <em>{station.ktw} KTW · {station.rtw} RTW</em>
              </button>
            ))}
            {unassignedEmployeeCount > 0 && (
              <div className="station-summary-card muted">
                <MapPinned size={17} />
                <span>
                  <strong>Ohne Wache</strong>
                  <small>{unassignedEmployeeCount} Profile</small>
                </span>
                <em>bitte zuweisen</em>
              </div>
            )}
          </div>
          <div className="admin-list employee-list">
            {visibleEmployees.map((item) => (
              <div className={`admin-row employee-row ${item.active ? '' : 'employee-row-inactive'}`} key={item.id}>
                <div className="employee-main">
                  <span className="employee-avatar">{(item.name || '?').slice(0, 1).toUpperCase()}</span>
                  <div>
                    <strong>{item.name}</strong>
                    <span>{qualificationLabel(item.qualification)} · {roleLabel(item.role)}</span>
                    <small>{stationLabel(item.station)} · {vehicleScopeLabel(item.vehicle_scope)}</small>
                  </div>
                </div>
                <span className={`status-pill ${item.active ? 'status-active' : 'status-locked'}`}>{item.active ? 'aktiv' : 'gesperrt'}</span>
                <div className="employee-controls">
                  <select value={item.qualification || ''} onChange={(event) => updateEmployee(item, { qualification: event.target.value })} aria-label={`Qualifikation von ${item.name}`}>
                    {EMPLOYEE_QUALIFICATION_OPTIONS.map((qualification) => (
                      <option key={qualification.value || 'none'} value={qualification.value}>{qualification.label}</option>
                    ))}
                  </select>
                  <select value={item.station || ''} onChange={(event) => updateEmployee(item, { station: event.target.value })} aria-label={`Rettungswache von ${item.name}`}>
                    {EMPLOYEE_STATION_OPTIONS.map((station) => (
                      <option key={station.value || 'none'} value={station.value}>{station.label}</option>
                    ))}
                  </select>
                  <select value={item.vehicle_scope || ''} onChange={(event) => updateEmployee(item, { vehicle_scope: event.target.value })} aria-label={`Einsatzmittel von ${item.name}`}>
                    {EMPLOYEE_VEHICLE_OPTIONS.map((vehicle) => (
                      <option key={vehicle.value || 'none'} value={vehicle.value}>{vehicle.label}</option>
                    ))}
                  </select>
                  <select value={item.role} onChange={(event) => updateEmployee(item, { role: event.target.value })}>
                    {EMPLOYEE_ROLE_OPTIONS.map((role) => (
                      <option key={role.value} value={role.value}>{role.label}</option>
                    ))}
                  </select>
                </div>
                <div className="employee-actions">
                  <button type="button" onClick={() => updateEmployee(item, { active: !item.active })}>
                    {item.active ? 'Sperren' : 'Aktivieren'}
                  </button>
                  <button type="button" onClick={() => updateEmployee(item, { reset_password: true })}>
                    <RotateCcw size={16} /> OTP
                  </button>
                  <button type="button" className="danger-button" onClick={() => deleteEmployee(item)} aria-label={`${item.name} löschen`}>
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
            {!visibleEmployees.length && (
              <div className="empty-state compact-empty-state">
                Keine Mitarbeiter gefunden.
              </div>
            )}
          </div>
          <div className="employee-insight-grid">
            <div className="employee-insight-card">
              <CheckCircle2 size={18} />
              <div>
                <strong>{activeEmployeeCount} aktiv</strong>
                <span>{lockedEmployeeCount} gesperrt</span>
              </div>
            </div>
            <div className="employee-insight-card">
              <ShieldCheck size={18} />
              <div>
                <strong>{adminEmployeeCount} Admins</strong>
                <span>{employees.length - adminEmployeeCount} weitere Profile</span>
              </div>
            </div>
            <div className="employee-insight-card">
              <AlertTriangle size={18} />
              <div>
                <strong>{privacyWarningCount} Hinweise</strong>
                <span>{privacyOkCount} Datenschutzpunkte ok</span>
              </div>
            </div>
            <div className="employee-insight-card">
              <MessageSquare size={18} />
              <div>
                <strong>{openFeedbackCount} offen</strong>
                <span>{feedbackItems.length} Meldungen insgesamt</span>
              </div>
            </div>
          </div>
        </article>

        <article className="work-panel admin-card privacy-admin-card">
          <div className="section-head">
            <div>
              <h2>Datenschutz</h2>
              <p>Verschlüsselung, Aufbewahrung und Löschläufe</p>
            </div>
            <span>{privacy?.encryption?.enabled ? 'Verschlüsselung aktiv' : 'Prüfen'}</span>
          </div>
          <div className="privacy-summary-grid">
            <div className="privacy-summary-item">
              <ShieldCheck size={18} />
              <div>
                <strong>Speicher-Schutz</strong>
                <span>{privacy?.encryption?.provider || 'wird geladen'}</span>
              </div>
            </div>
            <div className="privacy-summary-item">
              <Lock size={18} />
              <div>
                <strong>Schlüsselquelle</strong>
                <span>{privacy?.encryption?.key_source || '-'}</span>
              </div>
            </div>
            <div className="privacy-summary-item">
              <Activity size={18} />
              <div>
                <strong>Sitzungssperre</strong>
                <span>{privacy?.session_minutes || 30} Minuten Backend · 20 Minuten Oberfläche</span>
              </div>
            </div>
            <div className="privacy-summary-item">
              <ClipboardList size={18} />
              <div>
                <strong>Audit-Log</strong>
                <span>{privacy?.audit_events || 0} Ereignisse · {privacy?.security_log_retention_days || 180} Tage</span>
              </div>
            </div>
          </div>

          <div className="privacy-settings-panel">
            <label className="setting-field">
              <span>Einsatzdaten</span>
              <input value={retentionDays} onChange={(event) => setRetentionDays(event.target.value)} inputMode="numeric" />
              <small>Tage Aufbewahrung</small>
            </label>
            <label className="setting-field">
              <span>Sicherheitslogs</span>
              <input value={securityLogRetentionDays} onChange={(event) => setSecurityLogRetentionDays(event.target.value)} inputMode="numeric" />
              <small>Tage Aufbewahrung</small>
            </label>
            <label className="setting-toggle">
              <input
                type="checkbox"
                checked={externalMapsEnabled}
                onChange={(event) => setExternalMapsEnabled(event.target.checked)}
              />
              <span>
                <strong>Externe Kartenlinks</strong>
                <small>{externalMapsEnabled ? 'aktiviert' : 'deaktiviert'}</small>
              </span>
            </label>
            <button type="button" onClick={saveRetention}><Save size={17} /> Speichern</button>
          </div>

          <div className="privacy-actions">
            <button type="button" className="danger-button" onClick={purgeExpiredCases}>
              <Trash2 size={16} /> Abgelaufene Fälle löschen
            </button>
            <button type="button" className="danger-button" onClick={purgeSecurityEvents}>
              <Trash2 size={16} /> Alte Logs löschen
            </button>
          </div>

          <div className="privacy-checklist">
            {(privacy?.checklist || []).map((item) => (
              <div className={`privacy-check privacy-${item.status}`} key={item.label}>
                <strong>{item.label}</strong>
                <span>{item.detail}</span>
              </div>
            ))}
          </div>
          <p className="muted">{privacy?.encryption?.production_hint}</p>
        </article>
      </section>

      <section className="admin-secondary-grid">
      <section className="work-panel admin-section-card updates-admin-card">
        <div className="section-head">
          <h2>Patch Notes & Updates</h2>
          <span>{(announcementData.patch_notes || []).length} Patch Notes · {(announcementData.planned_updates || []).length} geplant</span>
        </div>
        <div className="admin-announcement-grid">
          <article>
            <h3>Patch Note hinzufügen</h3>
            <div className="deploy-note-box">
              <div>
                <strong>Aktuelles Deploy</strong>
                <span>{releaseInfo?.sha ? `${releaseInfo.sha} · ${releaseInfo.label || 'Zeit unbekannt'}` : 'Release-Stand wird geladen'}</span>
              </div>
              <button type="button" onClick={addDeployPatchNote}>Deploy übernehmen</button>
            </div>
            <div className="inline-form announcement-form">
              <input value={patchDraft.published_at} onChange={(event) => setPatchDraft({ ...patchDraft, published_at: event.target.value })} placeholder="Datum/Uhrzeit, z.B. 14.07.2026 22:30" />
              <input value={patchDraft.title} onChange={(event) => setPatchDraft({ ...patchDraft, title: event.target.value })} placeholder="Titel" />
              <textarea value={patchDraft.body} onChange={(event) => setPatchDraft({ ...patchDraft, body: event.target.value })} rows={4} placeholder="Was wurde geändert?" />
              <button type="button" onClick={() => addAnnouncement('patch_notes')}>Hinzufügen</button>
            </div>
            <div className="admin-list compact-admin-list">
              {(announcementData.patch_notes || []).map((item, index) => (
                <div className="admin-row" key={`patch-${index}-${item.title}`}>
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.published_at} · {item.body}</span>
                  </div>
                  <button type="button" className="danger-button" onClick={() => removeAnnouncement('patch_notes', index)}>Entfernen</button>
                </div>
              ))}
            </div>
          </article>
          <article>
            <h3>Geplantes Update hinzufügen</h3>
            <div className="inline-form announcement-form">
              <input value={plannedDraft.published_at} onChange={(event) => setPlannedDraft({ ...plannedDraft, published_at: event.target.value })} placeholder="geplant für / Zeitraum" />
              <input value={plannedDraft.title} onChange={(event) => setPlannedDraft({ ...plannedDraft, title: event.target.value })} placeholder="Titel" />
              <textarea value={plannedDraft.body} onChange={(event) => setPlannedDraft({ ...plannedDraft, body: event.target.value })} rows={4} placeholder="Was ist geplant?" />
              <button type="button" onClick={() => addAnnouncement('planned_updates')}>Hinzufügen</button>
            </div>
            <div className="admin-list compact-admin-list">
              {(announcementData.planned_updates || []).map((item, index) => (
                <div className="admin-row" key={`planned-${index}-${item.title}`}>
                  <div>
                    <strong>{item.title}</strong>
                    <span>{item.published_at} · {item.body}</span>
                  </div>
                  <button type="button" className="danger-button" onClick={() => removeAnnouncement('planned_updates', index)}>Entfernen</button>
                </div>
              ))}
            </div>
          </article>
        </div>
        <div className="protocol-toolbar compact-toolbar">
          <button type="button" onClick={saveAnnouncements}>Patch Notes / Updates speichern</button>
        </div>
      </section>

      <section className="work-panel admin-section-card feedback-admin-card">
        <div className="section-head">
          <h2>Bugs/Wünsche</h2>
          <span>{feedbackItems.length} Meldungen · {feedbackCounts.offen || 0} offen</span>
        </div>
        <div className="feedback-summary">
          <button type="button" className={feedbackFilter === 'alle' ? 'active' : ''} onClick={() => setFeedbackFilter('alle')}>
            Alle <strong>{feedbackItems.length}</strong>
          </button>
          {FEEDBACK_STATUS_OPTIONS.map((statusValue) => (
            <button
              type="button"
              key={statusValue}
              className={feedbackFilter === statusValue ? 'active' : ''}
              onClick={() => setFeedbackFilter(statusValue)}
            >
              {feedbackStatusLabel(statusValue)} <strong>{feedbackCounts[statusValue] || 0}</strong>
            </button>
          ))}
        </div>
        <div className="admin-list feedback-admin-list">
          {feedbackItems.length === 0 ? (
            <p className="muted">Noch keine Meldungen vorhanden.</p>
          ) : visibleFeedbackItems.length === 0 ? (
            <p className="muted">Keine Meldungen in diesem Status.</p>
          ) : visibleFeedbackItems.map((item) => (
            <div className="admin-row feedback-admin-row" key={item.id}>
              <div>
                <strong>{item.kind}: {item.title}</strong>
                <span>{item.created_at} · {item.employee_name || 'unbekannt'}</span>
                <span className={feedbackStatusClass(item.status)}>{feedbackStatusLabel(item.status)}</span>
                <p>{item.message}</p>
              </div>
              <select value={item.status || 'offen'} onChange={(event) => answerFeedback(item, event.target.value)}>
                {FEEDBACK_STATUS_OPTIONS.map((statusValue) => (
                  <option key={statusValue} value={statusValue}>{feedbackStatusLabel(statusValue)}</option>
                ))}
              </select>
              <textarea
                value={feedbackAnswers[item.id] || ''}
                onChange={(event) => setFeedbackAnswers((current) => ({ ...current, [item.id]: event.target.value }))}
                rows={3}
                placeholder="Antwort an Mitarbeiter/in"
              />
              <button type="button" onClick={() => answerFeedback(item, item.status || 'beantwortet')}>Antwort speichern</button>
            </div>
          ))}
        </div>
      </section>

      <div className="admin-stack">
        <section className="work-panel admin-section-card">
          <div className="section-head">
            <h2>Fall-Datenschutz</h2>
            <span>{cases.length} Einsätze</span>
          </div>
          <div className="case-list">
            {cases.length === 0 ? (
              <p className="muted">Keine Fälle vorhanden.</p>
            ) : cases.slice(0, 12).map((item) => (
              <article className="case-row case-row-actions" key={item.id}>
                <div>
                  <strong>{item.summary}</strong>
                  <span>{item.completed_at} · {item.employee_name || 'anonym'}</span>
                </div>
                <span className={`status-pill status-${item.status}`}>{item.status}</span>
                <button type="button" onClick={() => anonymizeCase(item.id)}>Anonymisieren</button>
                <button type="button" className="danger-button" onClick={() => deleteCase(item.id)}>
                  <Trash2 size={16} /> Löschen
                </button>
              </article>
            ))}
          </div>
        </section>

        <details className="work-panel admin-section-card collapsible-panel log-admin-card">
          <summary>
            <span>
              <strong>Audit-Log</strong>
              <small>{auditEvents.length} Ereignisse</small>
            </span>
            <ChevronDown size={18} />
          </summary>
          <div className="audit-list collapsible-body">
            {auditEvents.length === 0 ? (
              <p className="muted">Noch keine Audit-Ereignisse vorhanden.</p>
            ) : auditEvents.slice(0, 10).map((event, index) => (
              <div className="audit-row" key={`${event.timestamp}-${index}`}>
                <strong>{event.action}</strong>
                <span>{event.timestamp} · {event.employee_name || 'System'} · {event.entity_type || '-'}</span>
              </div>
            ))}
          </div>
        </details>

        <details className="work-panel admin-section-card collapsible-panel log-admin-card">
          <summary>
            <span>
              <strong>Login-Historie</strong>
              <small>{loginEvents.length} Anmeldungen</small>
            </span>
            <ChevronDown size={18} />
          </summary>
          <div className="login-event-list collapsible-body">
            {loginEvents.length === 0 ? (
              <p className="muted">Noch keine Login-Daten vorhanden.</p>
            ) : loginEvents.slice(0, 20).map((event, index) => (
              <div className="login-event-row" key={`${event.timestamp}-${event.device_id}-${index}`}>
                <div>
                  <strong>{event.employee_name || 'Unbekannter Account'}</strong>
                  <span>{event.timestamp} · {event.source || 'login'}</span>
                </div>
                <div>
                  <strong>{event.device_name || 'Unbekanntes Gerät'}</strong>
                  <span>{event.device_id || '-'}</span>
                </div>
                <div>
                  <strong>{event.ip_address || 'Keine IP'}</strong>
                  <span title={event.user_agent || ''}>{event.user_agent || 'Kein Browser-Agent'}</span>
                </div>
              </div>
            ))}
          </div>
        </details>

        <details className="work-panel admin-section-card collapsible-panel log-admin-card">
          <summary>
            <span>
              <strong>Exporthistorie</strong>
              <small>{exportEvents.length} Ereignisse</small>
            </span>
            <ChevronDown size={18} />
          </summary>
          <div className="audit-list collapsible-body">
            {exportEvents.length === 0 ? (
              <p className="muted">Noch keine PDF- oder Druckereignisse im Audit-Log.</p>
            ) : exportEvents.slice(0, 12).map((event, index) => (
              <div className="audit-row" key={`export-${event.timestamp}-${index}`}>
                <strong>{event.action}</strong>
                <span>{event.timestamp} · {event.employee_name || 'System'} · {event.entity_id || event.entity_type || '-'}</span>
              </div>
            ))}
          </div>
        </details>
      </div>

      <div className="admin-stack">
        <section className="work-panel admin-section-card qs-admin-card">
          <div className="section-head">
            <h2>QS-Regeln</h2>
            <span>{qualityRules.length} aktiv</span>
          </div>
          <div className="rules-grid">
            {qualityRules.map((rule) => (
              <div className={`rule-card rule-${rule.severity}`} key={rule.id}>
                <strong>{rule.label}</strong>
                <span>{rule.section} · {rule.severity}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
      </section>
    </main>
  );
}

function CancellationView({ session, employee, onBack, onLogout, connectivity }) {
  const [statusText, setStatusText] = useState('');
  const [actionFeedback, setActionFeedback] = useState(null);
  const [cancellation, setCancellation] = useState(() => {
    const now = new Date();
    return {
      reason: '',
      case_number: '',
      unit: '',
      location: '',
      date: now.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }),
      time: now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }),
      patient_contact: 'kein Patientenkontakt',
      dispatcher: '',
      alternative_action: '',
      details: '',
      documented_by: employee?.name || ''
    };
  });
  const cancellationText = buildCancellationText(cancellation);

  function updateCancellation(key, value) {
    setCancellation((current) => ({ ...current, [key]: value }));
  }

  function appendCancellation(key, value) {
    if (!value) return;
    setCancellation((current) => ({
      ...current,
      [key]: current[key] ? `${current[key]}; ${value}` : value
    }));
  }

  function markCancellationFeedback(key, message) {
    setActionFeedback({ key, message });
    setStatusText(message);
    window.setTimeout(() => {
      setActionFeedback((current) => (current?.key === key ? null : current));
    }, 4200);
  }

  function downloadCancellationText() {
    downloadBlob(new Blob([cancellationText], { type: 'text/plain;charset=utf-8' }), 'Einsatzabbruch.txt');
    markCancellationFeedback('cancel-download', 'TXT wurde vorbereitet.');
  }

  function printCancellationText() {
    const opened = printTextDocument('Einsatzabbruch', cancellationText);
    markCancellationFeedback('cancel-print', opened ? 'Druckfenster wurde geöffnet.' : 'Druckfenster konnte nicht geöffnet werden.');
  }

  return (
    <main className="app-shell">
      <SystemStatus {...connectivity} />
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">Einsatz abgebrochen</div>
        </div>
        <div className="user-area">
          <UserMenu session={session} employee={employee} onLogout={onLogout} />
          <button className="header-button" type="button" onClick={onBack}>
            <Home size={16} /> Hauptmenü
          </button>
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {statusText && <div className="success-box">{statusText}</div>}

      <section className="work-panel cancellation-panel">
        <div className="section-head">
          <h2>Einsatz abgebrochen</h2>
          <span>Abbruchgrund und Verlauf dokumentieren</span>
        </div>
        <div className="form-grid">
          <label>
            Grund
            <select value={cancellation.reason} onChange={(event) => updateCancellation('reason', event.target.value)}>
              <option value="">Bitte auswählen</option>
              {cancellationReasons.map((reason) => <option key={reason} value={reason}>{reason}</option>)}
            </select>
          </label>
          <label>
            Patientenkontakt
            <select value={cancellation.patient_contact} onChange={(event) => updateCancellation('patient_contact', event.target.value)}>
              <option value="kein Patientenkontakt">kein Patientenkontakt</option>
              <option value="Patientenkontakt ohne Behandlung">Patientenkontakt ohne Behandlung</option>
              <option value="Patientenkontakt, Versorgung durch andere Einheit">Patientenkontakt, Versorgung durch andere Einheit</option>
              <option value="nicht beurteilbar">nicht beurteilbar</option>
            </select>
          </label>
          <label>
            Einsatznummer
            <input value={cancellation.case_number} onChange={(event) => updateCancellation('case_number', event.target.value)} />
          </label>
          <label>
            Rettungsmittel
            <input value={cancellation.unit} onChange={(event) => updateCancellation('unit', event.target.value)} placeholder="z.B. RTW 1, KTW, NEF" />
          </label>
          <label>
            Datum
            <input value={cancellation.date} onChange={(event) => updateCancellation('date', event.target.value)} />
          </label>
          <label>
            Uhrzeit
            <input value={cancellation.time} onChange={(event) => updateCancellation('time', event.target.value)} />
          </label>
          <label className="full-span">
            Einsatzort / Bereich
            <input value={cancellation.location} onChange={(event) => updateCancellation('location', event.target.value)} placeholder="Ort, Straße, Abschnitt oder Bereich" />
          </label>
          <label>
            Leitstelle / Rücksprache
            <input value={cancellation.dispatcher} onChange={(event) => updateCancellation('dispatcher', event.target.value)} placeholder="z.B. Leitstelle informiert, Funk, Telefon" />
          </label>
          <label>
            Weitere Veranlassung
            <input value={cancellation.alternative_action} onChange={(event) => updateCancellation('alternative_action', event.target.value)} placeholder="z.B. Ersatz-RTW, Technik, Führungskraft" />
          </label>
          <label className="quick-select">
            Rücksprache ergänzen
            <select value="" onChange={(event) => appendCancellation('dispatcher', event.target.value)}>
              <option value="">Schnellbaustein auswählen</option>
              {cancellationDispatcherSnippets.map((snippet) => <option key={snippet} value={snippet}>{snippet}</option>)}
            </select>
          </label>
          <label className="quick-select">
            Veranlassung ergänzen
            <select value="" onChange={(event) => appendCancellation('alternative_action', event.target.value)}>
              <option value="">Schnellbaustein auswählen</option>
              {cancellationAlternativeSnippets.map((snippet) => <option key={snippet} value={snippet}>{snippet}</option>)}
            </select>
          </label>
          <label className="full-span">
            Freitext / Verlauf
            <textarea value={cancellation.details} onChange={(event) => updateCancellation('details', event.target.value)} rows={5} placeholder="Was ist passiert? Warum war der Einsatz nicht möglich bzw. warum wurde abgebrochen?" />
          </label>
          <label className="full-span quick-select">
            Verlauf ergänzen
            <select value="" onChange={(event) => appendCancellation('details', event.target.value)}>
              <option value="">Schnellbaustein auswählen</option>
              {cancellationDetailSnippets.map((snippet) => <option key={snippet} value={snippet}>{snippet}</option>)}
            </select>
          </label>
          <label>
            Dokumentiert durch
            <input value={cancellation.documented_by} onChange={(event) => updateCancellation('documented_by', event.target.value)} />
          </label>
        </div>
        <div className="protocol-toolbar compact-toolbar">
          <button type="button" className={actionFeedback?.key === 'cancel-download' ? 'action-confirmed' : ''} onClick={downloadCancellationText}>
            {actionFeedback?.key === 'cancel-download' ? 'TXT vorbereitet' : 'TXT herunterladen'}
          </button>
          <button type="button" className={actionFeedback?.key === 'cancel-print' ? 'action-confirmed' : ''} onClick={printCancellationText}>
            {actionFeedback?.key === 'cancel-print' ? 'Druck geöffnet' : 'Drucken'}
          </button>
        </div>
        <textarea
          className="protocol-preview cancellation-preview"
          value={cancellationText}
          readOnly
          rows={16}
        />
      </section>
    </main>
  );
}

const emptyPatient = {
  patient: { patientengruppe: '', alter_wert: '', alter_einheit: 'Jahre', pat: {}, paediatrie: {} },
  vitalwerte: {},
  xabcde: {},
  samplers: {},
  opqrst: {},
  psyche: {},
  einweisung: {},
  amls: { excluded: [], custom_candidates: [], arbeitsdiagnose: '', leitsymptom: '', notizen: '' },
  massnahmen: { timeline: [], medikation: [] },
  reanimation: { shocks: [] },
  transport: {},
  einsatz: {},
  anfahrt: {},
  besatzung: { verantwortlicher: '', verantwortlicher_id: '', fahrer: '', fahrer_id: '', azubi: '', azubi_id: '', praktikant: '', praktikant_id: '' },
  uebergabe: {}
};

function patientWithCrewDefaults(patient, employee) {
  const shiftCrew = loadLocalShiftCrew(employee?.id);
  const nextPatient = { ...emptyPatient, ...(patient || {}) };
  nextPatient.besatzung = {
    ...(emptyPatient.besatzung || {}),
    ...(shiftCrew || {}),
    ...(nextPatient.besatzung || {}),
    verantwortlicher: nextPatient.besatzung?.verantwortlicher || shiftCrew?.verantwortlicher || employee?.name || '',
    verantwortlicher_id: nextPatient.besatzung?.verantwortlicher_id || shiftCrew?.verantwortlicher_id || employee?.id || ''
  };
  return nextPatient;
}

function ProtocolView({ session, employee, onSessionReplace, onBack, onLogout, connectivity, onSync, initialSection = 'patient', standaloneRefusal = false }) {
  const initialLocalDraft = loadLocalDraft(employee?.id);
  const skipNextDraftReload = useRef(false);
  const [patient, setPatient] = useState(emptyPatient);
  const [crewEmployees, setCrewEmployees] = useState([]);
  const [crewSwitch, setCrewSwitch] = useState({ open: false, target: null, password: '' });
  const [protocolSection, setProtocolSection] = useState(initialSection);
  const [protocolNavCollapsed, setProtocolNavCollapsed] = useState(
    () => localStorage.getItem('nana_protocol_nav_collapsed') === 'true'
  );
  const [xabcdeSection, setXabcdeSection] = useState('A');
  const [samplersSection, setSamplersSection] = useState('S1');
  const [opqrstSection, setOpqrstSection] = useState('O');
  const [selectedTraumaRegion, setSelectedTraumaRegion] = useState('');
  const [statusText, setStatusText] = useState('');
  const [actionFeedback, setActionFeedback] = useState(null);
  const [error, setError] = useState('');
  const [generatedProtocol, setGeneratedProtocol] = useState('');
  const [qualityResult, setQualityResult] = useState(null);
  const [forceFinish, setForceFinish] = useState(false);
  const [localDraft, setLocalDraft] = useState(initialLocalDraft);
  const [localDraftDecisionPending, setLocalDraftDecisionPending] = useState(Boolean(initialLocalDraft?.patient));
  const [draftReady, setDraftReady] = useState(false);
  const [amlsSuggestions, setAmlsSuggestions] = useState([]);
  const [calculator, setCalculator] = useState({ sop: 'Anaphylaxie (SOPKB0105)', age: '30', weight: '70', pregnant: 'Nein', bz: '55', rr_sys: '160', nrs: '7' });
  const [calculatorResult, setCalculatorResult] = useState(null);
  const [acceptedCalculatorMedication, setAcceptedCalculatorMedication] = useState(null);
  const [refusal, setRefusal] = useState(() => {
    const now = new Date();
    return {
      patient_name: '',
      presented_to: '',
      case_number: '',
      date: now.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }),
      time: now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }),
      refuse_treatment: true,
      refuse_transport: true,
      capacity_confirmed: true,
      advised_against: true,
      signature_refused: false,
      scope: '',
      reason: '',
      risks: 'Verschlechterung des Gesundheitszustands, verzögerte Diagnostik/Therapie, bleibende Gesundheitsschäden bis hin zu akuter Lebensgefahr',
      witness: ''
    };
  });

  function toggleProtocolNav() {
    setProtocolNavCollapsed((collapsed) => {
      const next = !collapsed;
      localStorage.setItem('nana_protocol_nav_collapsed', String(next));
      return next;
    });
  }
  const vitalwerte = patient.vitalwerte || {};
  const patientData = patient.patient || {};
  const isChild = patientData.patientengruppe === 'Kind';
  const childAgeMonths = isChild && patientData.alter_wert !== ''
    ? Number(patientData.alter_wert) * (patientData.alter_einheit === 'Jahre' ? 12 : 1)
    : null;
  const isNewborn = childAgeMonths !== null && childAgeMonths <= 1;
  const activeSamplersSections = isChild
    ? samplersSections.filter((section) => section.key !== 'S2')
    : samplersSections;
  const pediatricAgeGroup = childAgeMonths === null ? ''
    : childAgeMonths <= 1 ? 'Neugeborenes'
      : childAgeMonths < 12 ? 'Säugling'
        : childAgeMonths < 36 ? 'Kleinkind'
          : childAgeMonths < 72 ? 'Vorschulkind'
            : childAgeMonths < 144 ? 'Schulkind'
              : 'Jugendlicher';
  const pediatricGcsValues = ['gcs_augen', 'gcs_verbal', 'gcs_motorik'].map((key) => Number(patientData.paediatrie?.[key] || 0));
  const pediatricGcsComplete = pediatricGcsValues.every((value) => value > 0);
  const pediatricGcsTotal = pediatricGcsComplete ? pediatricGcsValues.reduce((sum, value) => sum + value, 0) : null;
  const xabcde = patient.xabcde || {};
  const crew = patient.besatzung || {};
  const samplers = patient.samplers || {};
  const opqrst = patient.opqrst || {};
  const psyche = patient.psyche || {};
  const massnahmen = patient.massnahmen || { timeline: [], medikation: [] };
  const reanimation = patient.reanimation || { shocks: [] };
  const amls = patient.amls || {};
  const uebergabe = patient.uebergabe || {};
  const amlsCandidates = Array.isArray(amls.custom_candidates) ? amls.custom_candidates : [];
  const amlsExcluded = Array.isArray(amls.excluded) ? amls.excluded : [];
  const amlsExcludedNames = new Set(amlsExcluded.map((item) => (
    typeof item === 'string' ? item : item?.diagnose || item?.name || ''
  )).filter(Boolean));
  const amlsVisibleCandidates = amlsSuggestions.length > 0 ? amlsSuggestions : amlsCandidates.map((item) => {
    const candidate = typeof item === 'string' ? { diagnose: item } : item || {};
    return {
      name: candidate.diagnose || candidate.name || '',
      category: 'Eigene Ergänzung',
      rationale: candidate.hinweis || candidate.rationale || 'Manuell ergänzt',
      conflicts: [],
      status: amlsExcludedNames.has(candidate.diagnose || candidate.name || '') ? 'excluded' : 'matching',
    };
  }).filter((item) => item.name);
  const amlsRemainingCandidates = amlsVisibleCandidates.filter((item) => !amlsExcludedNames.has(item.name));
  const amlsMatchingCount = amlsVisibleCandidates.filter((item) => !amlsExcludedNames.has(item.name) && !(item.conflicts || []).length).length;
  const amlsCheckCount = amlsVisibleCandidates.filter((item) => !amlsExcludedNames.has(item.name) && (item.conflicts || []).length).length;
  const sinnhaftPreviewRows = sinnhaftRows(patient);
  const refusalText = buildPatientRefusalText(patient, refusal);
  const xabcdeCompletedCount = xabcdeSections.filter((section) => xabcdeSectionComplete(section.key)).length;
  const xabcdeOpenSections = xabcdeSections.filter((section) => !xabcdeSectionComplete(section.key)).map((section) => section.key);
  const samplersCompletedCount = activeSamplersSections.filter((section) => samplersSectionComplete(section.key)).length;
  const samplersOpenSections = activeSamplersSections.filter((section) => !samplersSectionComplete(section.key)).map((section) => section.label);
  const amlsReadiness = amls.arbeitsdiagnose
    ? { level: 'ok', text: `Arbeitsdiagnose gesetzt: ${amls.arbeitsdiagnose}` }
    : amlsRemainingCandidates.length === 1
      ? { level: 'warning', text: `Ein Kandidat verbleibt: ${amlsRemainingCandidates[0].name}` }
      : { level: 'info', text: 'Arbeitsdiagnose noch offen.' };
  const protocolNavItems = [
    {
      key: 'besatzung',
      label: 'Besatzung',
      icon: UserPlus,
      complete: hasValue(crew.verantwortlicher) && hasValue(crew.fahrer)
    },
    {
      key: 'patient',
      label: 'Patient',
      icon: UserRound,
      complete: hasValue(patientData.patientengruppe) && (!isChild || (hasValue(patientData.alter_wert) && hasValue(patientData.medizinisches_gewicht)))
    },
    {
      key: 'vitalwerte',
      label: 'Vitalwerte',
      icon: HeartPulse,
      complete: ['rr_sys', 'rr_dia', 'puls', 'spo2', 'af'].every((key) => hasValue(vitalwerte[key]))
        && (isChild ? pediatricGcsComplete : hasValue(vitalwerte.gcs))
    },
    {
      key: 'xabcde',
      label: 'xABCDE',
      icon: Stethoscope,
      complete: xabcdeCompletedCount === xabcdeSections.length
    },
    {
      key: 'samplers',
      label: 'SAMPLERS',
      icon: ClipboardList,
      complete: samplersCompletedCount === activeSamplersSections.length
    },
    {
      key: 'opqrst',
      label: 'OPQRST',
      icon: Activity,
      complete: hasValue(opqrst.schmerz_vorhanden)
        && opqrstSections.every((section) => opqrstSectionComplete(section.key))
    },
    { key: 'amls', label: 'Diagnosehilfe', icon: Search, complete: hasValue(amls.arbeitsdiagnose) },
    {
      key: 'psyche',
      label: 'Psyche',
      icon: Brain,
      complete: hasValue(psyche.zustand)
        && hasValue(psyche.eigengefaehrdung)
        && hasValue(psyche.fremdgefaehrdung)
        && hasValue(psyche.unterbringungsweg)
    },
    { key: 'rechner', label: 'Rechner', icon: Calculator, complete: Boolean(calculatorResult) },
    {
      key: 'massnahmen',
      label: 'Maßnahmen',
      icon: Pill,
      complete: (massnahmen.timeline || []).length > 0 || (massnahmen.medikation || []).length > 0
    },
    {
      key: 'reanimation',
      label: 'Reanimation',
      icon: HeartPulse,
      complete: Boolean(reanimation.active && hasValue(reanimation.outcome))
    },
    {
      key: 'abschluss',
      label: 'Übergabe',
      icon: ShieldCheck,
      complete: hasValue(uebergabe.ziel) && hasValue(uebergabe.text)
    },
    { key: 'protokoll', label: 'Dokumentation', icon: FileText, complete: hasValue(generatedProtocol) }
  ];

  const selectableCrewEmployees = useMemo(() => crewEmployees.filter((item) => item.active !== false), [crewEmployees]);
  const transportLeaderOptions = useMemo(() => selectableCrewEmployees.filter((item) => !['azubi', 'bufdi', 'praktikant'].includes(item.role)), [selectableCrewEmployees]);
  const driverOptions = transportLeaderOptions;
  const azubiOptions = useMemo(() => selectableCrewEmployees.filter((item) => item.role === 'azubi'), [selectableCrewEmployees]);
  const traineeOptions = useMemo(() => selectableCrewEmployees.filter((item) => ['praktikant', 'bufdi'].includes(item.role)), [selectableCrewEmployees]);

  function employeeById(employeeId) {
    return selectableCrewEmployees.find((item) => item.id === employeeId);
  }

  useEffect(() => {
    api('/api/auth/employees')
      .then((data) => setCrewEmployees(data.employees || []))
      .catch(() => setCrewEmployees([]));
  }, []);

  useEffect(() => {
    if (skipNextDraftReload.current) {
      skipNextDraftReload.current = false;
      setDraftReady(true);
      return;
    }
    api('/api/draft', {}, session.token)
      .then((data) => {
        setPatient(patientWithCrewDefaults(data.patient, employee));
        setDraftReady(true);
        const syncTime = data.updated_at || new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        onSync?.(syncTime);
      })
      .catch((err) => {
        setError(`${err.message} Patientendaten werden aus Datenschutzgründen nicht lokal im Browser zwischengespeichert.`);
        setDraftReady(true);
      });
  }, [session.token, employee?.id]);

  useEffect(() => {
    if (!draftReady || localDraftDecisionPending) return;
    const saved = saveLocalDraft(employee?.id, patient);
    if (saved) {
      setLocalDraft(saved);
    }
  }, [patient, draftReady, localDraftDecisionPending, employee?.id]);

  useEffect(() => {
    if (protocolSection === 'amls' && amlsSuggestions.length === 0) {
      loadAmlsSuggestions();
    }
  }, [protocolSection]);

  useEffect(() => {
    if (isChild && samplersSection === 'S2') {
      setSamplersSection('S1');
    }
  }, [isChild, samplersSection]);

  function restoreLocalDraft() {
    const draft = loadLocalDraft(employee?.id);
    if (draft?.patient) {
      setPatient(patientWithCrewDefaults(draft.patient, employee));
      setLocalDraft(draft);
      setLocalDraftDecisionPending(false);
      setStatusText(`Lokaler Entwurf wiederhergestellt: ${new Date(draft.updatedAt).toLocaleString('de-DE')}`);
    }
  }

  function discardLocalDraft() {
    clearLocalDraft(employee?.id);
    setLocalDraft(null);
    setLocalDraftDecisionPending(false);
    setStatusText('Lokaler Entwurf wurde verworfen.');
  }

  function updateVital(key, value) {
    setPatient((current) => ({
      ...current,
      vitalwerte: {
        ...(current.vitalwerte || {}),
        [key]: value
      }
    }));
  }

  function updatePatientData(key, value) {
    setPatient((current) => ({
      ...current,
      patient: {
        ...(current.patient || {}),
        [key]: value
      }
    }));
  }

  function updateCrew(key, value) {
    setPatient((current) => ({
      ...current,
      besatzung: {
        ...(current.besatzung || {}),
        [key]: value
      }
    }));
    saveLocalShiftCrew(employee?.id, { ...(patient.besatzung || {}), [key]: value });
  }

  function selectCrewEmployee(nameKey, idKey, employeeId) {
    const selectedEmployee = employeeById(employeeId);
    replaceCrew({
      [idKey]: selectedEmployee?.id || '',
      [nameKey]: selectedEmployee?.name || ''
    });
  }

  function replaceCrew(nextCrew) {
    setPatient((current) => ({
      ...current,
      besatzung: {
        ...(current.besatzung || {}),
        ...nextCrew
      }
    }));
    saveLocalShiftCrew(employee?.id, { ...(patient.besatzung || {}), ...nextCrew });
  }

  function swapTransportLeaderWithDriver() {
    if (!hasValue(crew.verantwortlicher) || !hasValue(crew.fahrer)) {
      setStatusText('Bitte zuerst Transportführer/in und Fahrer/in eintragen.');
      return;
    }
    if (!crew.fahrer_id) {
      setStatusText('Bitte Fahrer/in aus der Mitarbeiterliste auswählen, damit das Passwort geprüft werden kann.');
      return;
    }
    setCrewSwitch({ open: true, target: employeeById(crew.fahrer_id), password: '' });
  }

  async function confirmTransportLeaderSwitch(event) {
    event.preventDefault();
    const target = crewSwitch.target;
    if (!target?.id) {
      setError('Neuer Transportführer wurde nicht eindeutig ausgewählt.');
      return;
    }
    setError('');
    setStatusText('');
    const nextCrew = {
      verantwortlicher: crew.fahrer || target.name,
      verantwortlicher_id: target.id,
      fahrer: crew.verantwortlicher || employee?.name || '',
      fahrer_id: crew.verantwortlicher_id || employee?.id || '',
      azubi: crew.azubi || '',
      azubi_id: crew.azubi_id || '',
      praktikant: crew.praktikant || '',
      praktikant_id: crew.praktikant_id || ''
    };
    const nextPatient = { ...patient, besatzung: nextCrew };
    try {
      const result = await api('/api/auth/reauth', {
        method: 'POST',
        body: JSON.stringify({ employee_id: target.id, password: crewSwitch.password, restore_shift: true, ...browserDeviceInfo() })
      });
      await api('/api/draft', {
        method: 'PUT',
        body: JSON.stringify({ patient: nextPatient })
      });
      skipNextDraftReload.current = true;
      setPatient(nextPatient);
      saveLocalShiftCrew(result.employee?.id, nextCrew);
      saveLocalDraft(result.employee?.id, nextPatient);
      setLocalDraft(loadLocalDraft(result.employee?.id));
      onSessionReplace?.(result);
      setCrewSwitch({ open: false, target: null, password: '' });
      setStatusText(`${target.name} ist jetzt als Transportführer/in angemeldet.`);
    } catch (err) {
      setError(err.message);
    }
  }

  function renderCrewSelector(label, nameKey, idKey, options, placeholder) {
    return (
      <label>
        {label}
        <div className="crew-select-row">
          <input
            value={crew[nameKey] || ''}
            onChange={(event) => replaceCrew({ [nameKey]: event.target.value, [idKey]: '' })}
            placeholder={placeholder}
          />
          <select value={crew[idKey] || ''} onChange={(event) => selectCrewEmployee(nameKey, idKey, event.target.value)}>
            <option value="">Auswählen</option>
            {options.map((item) => (
              <option key={`${idKey}-${item.id}`} value={item.id}>
                {item.name} · {roleLabel(item.role)}
              </option>
            ))}
          </select>
        </div>
      </label>
    );
  }

  function renderCrewSection() {
    return (
      <>
        <div className="section-head">
          <h2>Besatzung</h2>
          <span>Transportführer/in pro Einsatz wechselbar</span>
        </div>
        <div className="form-grid crew-grid">
          {renderCrewSelector('Transportführer/in', 'verantwortlicher', 'verantwortlicher_id', transportLeaderOptions, 'Name Transportführer/in')}
          {renderCrewSelector('Fahrer/in', 'fahrer', 'fahrer_id', driverOptions, 'Name Fahrer/in')}
          {renderCrewSelector('Azubi', 'azubi', 'azubi_id', azubiOptions, 'optional')}
          {renderCrewSelector('Praktikant/in / BuFDi', 'praktikant', 'praktikant_id', traineeOptions, 'optional')}
        </div>
        <div className="crew-actions">
          <button type="button" className="crew-swap-button" onClick={swapTransportLeaderWithDriver} title="Transportführer/in und Fahrer/in tauschen">
            <ArrowRightLeft size={18} />
          </button>
          <button type="button" onClick={() => replaceCrew({ verantwortlicher: employee?.name || '', verantwortlicher_id: employee?.id || '' })}>Login als TF setzen</button>
        </div>
        {crewSwitch.open && (
          <form className="crew-switch-panel" onSubmit={confirmTransportLeaderSwitch}>
            <div>
              <strong>{crewSwitch.target?.name || crew.fahrer} wird neuer Transportführer</strong>
              <span>Bitte Passwort eingeben, danach ist diese Person oben rechts angemeldet.</span>
            </div>
            <input
              type="password"
              value={crewSwitch.password}
              onChange={(event) => setCrewSwitch((current) => ({ ...current, password: event.target.value }))}
              placeholder="Passwort neuer TF"
              autoFocus
            />
            <button type="submit">Wechsel bestätigen</button>
            <button type="button" onClick={() => setCrewSwitch({ open: false, target: null, password: '' })}>Abbrechen</button>
          </form>
        )}
      </>
    );
  }

  function updatePediatricGroup(group, key, value) {
    setPatient((current) => ({
      ...current,
      patient: {
        ...(current.patient || {}),
        [group]: {
          ...((current.patient || {})[group] || {}),
          [key]: value
        }
      }
    }));
  }

  function selectPatientGroup(nextGroup) {
    const currentGroup = patientData.patientengruppe;
    if (currentGroup && currentGroup !== nextGroup) {
      const confirmed = window.confirm(`Zu ${nextGroup} wechseln? Nicht passende Angaben des bisherigen Modus werden entfernt.`);
      if (!confirmed) return;
    }
    setPatient((current) => {
      const next = {
        ...current,
        patient: {
          ...(current.patient || {}),
          patientengruppe: nextGroup
        }
      };
      if (nextGroup === 'Kind') {
        next.vitalwerte = { ...(next.vitalwerte || {}) };
        delete next.vitalwerte.gcs;
        delete next.vitalwerte.gcs_status;
        next.samplers = { ...(next.samplers || {}) };
        delete next.samplers.schwangerschaft;
      } else {
        next.patient = { ...next.patient, alter_wert: '', alter_einheit: 'Jahre', pat: {}, paediatrie: {} };
        next.samplers = { ...(next.samplers || {}) };
        Object.keys(pediatricRiskFactorLabels).forEach((key) => delete next.samplers[key]);
      }
      return next;
    });
    setAmlsSuggestions([]);
  }

  function updateApgar(minute, key, value) {
    const current = patientData.paediatrie?.apgar_details || {};
    updatePediatricGroup('paediatrie', 'apgar_details', {
      ...current,
      [minute]: { ...(current[minute] || {}), [key]: value }
    });
  }

  function apgarTotal(minute) {
    const values = Object.values(patientData.paediatrie?.apgar_details?.[minute] || {});
    return values.length === 5 && values.every((value) => value !== '')
      ? values.reduce((sum, value) => sum + Number(value), 0)
      : null;
  }

  function renderVitalStatus(statusKey, label) {
    return (
      <label className="vital-status-field">
        {label && <span>{label}</span>}
        <select value={vitalwerte[statusKey] || 'Keine Angabe'} onChange={(event) => updateVital(statusKey, event.target.value)}>
          {vitalStatusOptions[statusKey].map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        {vitalwerte[statusKey] === CUSTOM_STATUS && (
          <input
            className="inline-custom-input"
            value={vitalwerte[`${statusKey}_custom`] || ''}
            onChange={(event) => updateVital(`${statusKey}_custom`, event.target.value)}
            placeholder="Eigene Einordnung eintragen"
          />
        )}
      </label>
    );
  }

  function renderVitalPair({ title, valueKey, statusKey, inputMode = 'numeric', placeholder = 'Messwert optional' }) {
    return (
      <fieldset className="vital-pair">
        <legend>{title}</legend>
        <div className="vital-pair-grid">
          <label>
            Messwert optional
            <input
              value={vitalwerte[valueKey] || ''}
              onChange={(event) => updateVital(valueKey, event.target.value)}
              inputMode={inputMode}
              placeholder={placeholder}
            />
          </label>
          {renderVitalStatus(statusKey, 'Einordnung')}
        </div>
      </fieldset>
    );
  }

  function renderBloodPressurePair() {
    return (
      <fieldset className="vital-pair">
        <legend>RR</legend>
        <div className="vital-pair-grid vital-bp-grid">
          <label>
            systolisch optional
            <input value={vitalwerte.rr_sys || ''} onChange={(event) => updateVital('rr_sys', event.target.value)} inputMode="numeric" placeholder="sys" />
          </label>
          <label>
            diastolisch optional
            <input value={vitalwerte.rr_dia || ''} onChange={(event) => updateVital('rr_dia', event.target.value)} inputMode="numeric" placeholder="dia" />
          </label>
          {renderVitalStatus('rr_status', 'Einordnung')}
        </div>
      </fieldset>
    );
  }

  function updateXabcde(key, value) {
    setPatient((current) => ({
      ...current,
      xabcde: {
        ...(current.xabcde || {}),
        [key]: value
      }
    }));
  }

  function toggleXabcdeFlag(key) {
    updateXabcde(key, !Boolean(xabcde[key]));
  }

  function traumaFindings() {
    return Array.isArray(xabcde.trauma_befunde) ? xabcde.trauma_befunde : [];
  }

  function selectTraumaRegion(region, side) {
    const id = `${side}:${region}`;
    setPatient((current) => {
      const currentX = current.xabcde || {};
      const findings = Array.isArray(currentX.trauma_befunde) ? currentX.trauma_befunde : [];
      if (findings.some((item) => item.id === id)) {
        setSelectedTraumaRegion((selected) => selected === id ? '' : selected);
        return {
          ...current,
          xabcde: {
            ...currentX,
            trauma_befunde: findings.filter((item) => item.id !== id)
          }
        };
      }
      setSelectedTraumaRegion(id);
      return {
        ...current,
        xabcde: {
          ...currentX,
          bodycheck: 'Auffällig',
          trauma_befunde: [...findings, { id, region, side, verletzungsarten: [], blutung: '', notiz: '' }]
        }
      };
    });
  }

  function updateTraumaFinding(id, key, value) {
    setPatient((current) => {
      const currentX = current.xabcde || {};
      const findings = Array.isArray(currentX.trauma_befunde) ? currentX.trauma_befunde : [];
      return { ...current, xabcde: { ...currentX, trauma_befunde: findings.map((item) => item.id === id ? { ...item, [key]: value } : item) } };
    });
  }

  function toggleTraumaInjury(id, injuryType) {
    const finding = traumaFindings().find((item) => item.id === id);
    const values = Array.isArray(finding?.verletzungsarten) ? finding.verletzungsarten : [];
    updateTraumaFinding(id, 'verletzungsarten', values.includes(injuryType) ? values.filter((item) => item !== injuryType) : [...values, injuryType]);
  }

  function removeTraumaFinding(id) {
    updateXabcde('trauma_befunde', traumaFindings().filter((item) => item.id !== id));
    if (selectedTraumaRegion === id) setSelectedTraumaRegion('');
  }

  function bodyMap(side) {
    const selectedIds = new Set(traumaFindings().map((item) => item.id));
    const region = (key, element) => (
      <g className={`body-region ${selectedIds.has(`${side}:${key}`) ? 'marked' : ''}`} onClick={() => selectTraumaRegion(key, side)} onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          selectTraumaRegion(key, side);
        }
      }} role="button" tabIndex="0" key={key}>
        {element}
        <title>{traumaBodyRegions[key]?.label}</title>
      </g>
    );
    return <div className="body-map-view">
      <strong>{side === 'vorne' ? 'Vorne' : 'Hinten'}</strong>
      <svg viewBox="0 0 240 500" aria-label={`Körperskizze ${side}`}>
        {side === 'vorne'
          ? region('gesicht', <path d="M92 24 Q120 5 148 24 L145 62 Q137 84 120 90 Q103 84 95 62 Z" />)
          : region('hinterkopf', <path d="M92 24 Q120 5 148 24 L145 65 Q137 86 120 90 Q103 86 95 65 Z" />)}
        {region('hals', <path d="M108 88 L132 88 L136 112 Q120 122 104 112 Z" />)}
        {region('schulter_rechts', <path d="M104 108 L67 120 Q54 128 48 145 L78 154 L105 133 Z" />)}
        {region('schulter_links', <path d="M136 108 L173 120 Q186 128 192 145 L162 154 L135 133 Z" />)}
        {side === 'vorne' ? <>
          {region('thorax_rechts', <path d="M78 125 Q98 112 118 118 L118 218 Q96 220 82 205 Z" />)}
          {region('thorax_links', <path d="M122 118 Q142 112 162 125 L158 205 Q144 220 122 218 Z" />)}
          {region('abdomen_rechts', <path d="M83 208 Q100 216 118 214 L118 286 Q98 288 86 276 Z" />)}
          {region('abdomen_links', <path d="M122 214 Q140 216 157 208 L154 276 Q142 288 122 286 Z" />)}
          {region('becken', <path d="M85 274 Q120 292 155 274 L164 326 Q120 348 76 326 Z" />)}
        </> : <>
          {region('ruecken_oben', <path d="M78 125 Q120 105 162 125 L157 218 Q120 232 83 218 Z" />)}
          {region('ruecken_unten', <path d="M83 211 Q120 225 157 211 L154 282 Q120 296 86 282 Z" />)}
          {region('gesaess_rechts', <path d="M86 276 Q101 286 118 284 L118 337 Q94 344 76 326 Z" />)}
          {region('gesaess_links', <path d="M122 284 Q139 286 154 276 L164 326 Q146 344 122 337 Z" />)}
        </>}
        {region('oberarm_rechts', <path d="M52 139 L78 148 L64 231 L38 225 Z" />)}
        {region('ellenbogen_rechts', <ellipse cx="49" cy="237" rx="16" ry="14" />)}
        {region('unterarm_rechts', <path d="M38 247 L62 246 L47 337 L22 332 Z" />)}
        {region('hand_rechts', <path d="M21 329 L48 334 L46 374 Q32 389 17 371 Z" />)}
        {region('oberarm_links', <path d="M162 148 L188 139 L202 225 L176 231 Z" />)}
        {region('ellenbogen_links', <ellipse cx="191" cy="237" rx="16" ry="14" />)}
        {region('unterarm_links', <path d="M178 246 L202 247 L218 332 L193 337 Z" />)}
        {region('hand_links', <path d="M192 334 L219 329 L223 371 Q208 389 194 374 Z" />)}
        {region('oberschenkel_rechts', <path d="M77 323 Q96 338 117 334 L112 409 L72 409 Z" />)}
        {region('knie_rechts', <ellipse cx="91" cy="418" rx="21" ry="15" />)}
        {region('unterschenkel_rechts', <path d="M72 427 L110 427 L104 487 L76 487 Z" />)}
        {region('fuss_rechts', <path d="M75 482 L104 482 L112 496 L65 496 Z" />)}
        {region('oberschenkel_links', <path d="M123 334 Q144 338 163 323 L168 409 L128 409 Z" />)}
        {region('knie_links', <ellipse cx="149" cy="418" rx="21" ry="15" />)}
        {region('unterschenkel_links', <path d="M130 427 L168 427 L164 487 L136 487 Z" />)}
        {region('fuss_links', <path d="M136 482 L165 482 L175 496 L128 496 Z" />)}
      </svg>
    </div>;
  }

  function renderXabcdeSelect(key, label) {
    const options = xabcdeOptions[key];
    return (
      <label>
        {label}
        <select value={xabcde[key] || options[0]} onChange={(event) => updateXabcde(key, event.target.value)}>
          {options.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
      </label>
    );
  }

  function xabcdeSectionComplete(sectionKey) {
    if (sectionKey === 'X') return hasValue(xabcde.blutung);
    if (sectionKey === 'A') return hasValue(xabcde.atemweg) && hasValue(xabcde.hws);
    if (sectionKey === 'B') return hasValue(xabcde.atmung) && hasValue(xabcde.atemgeraeusche);
    if (sectionKey === 'C') return hasValue(xabcde.haut) && hasValue(xabcde.rekap) && hasValue(xabcde.pulsqualitaet);
    if (sectionKey === 'D') return hasValue(xabcde.avpu) && hasValue(xabcde.pupillen);
    if (sectionKey === 'E') return hasValue(xabcde.bodycheck) && (xabcde.bodycheck !== 'Auffällig' || hasValue(xabcde.bodycheck_text));
    return false;
  }

  function befastStatus() {
    const keys = ['befast_balance', 'befast_eyes', 'befast_face', 'befast_arms', 'befast_speech'];
    const documented = keys.filter((key) => hasValue(xabcde[key]));
    const positives = keys.map((key) => xabcde[key]).filter((value) => hasValue(value) && !befastNormalValues.has(value));
    if (positives.length > 0) return { level: 'critical', text: `BE-FAST auffällig: ${positives.join(' · ')}` };
    if (documented.length === keys.length) return { level: 'ok', text: 'BE-FAST ohne dokumentierte Auffälligkeit' };
    return null;
  }

  function samplersSectionComplete(sectionKey) {
    if (sectionKey === 'S1') return hasValue(samplers.symptome);
    if (sectionKey === 'A') return hasValue(formatSelectedAllergies(samplers));
    if (sectionKey === 'M') return hasValue(formatSelectedMedication(samplers));
    if (sectionKey === 'P') return hasValue(samplers.vorgeschichte);
    if (sectionKey === 'L') return hasValue(formatLastMeal(samplers)) || hasValue(samplers.letzte_medikamenteneinnahme);
    if (sectionKey === 'E') return hasValue(samplers.ereignis);
    if (sectionKey === 'R') return hasValue(formatRiskFactors(samplers));
    if (sectionKey === 'S2') return hasValue(formatPregnancyStatus(samplers)) || samplers.schwangerschaft === 'Nicht relevant';
    return false;
  }

  function renderXabcdeContent() {
    if (xabcdeSection === 'X') {
      return (
        <fieldset className="xabcde-panel">
          <legend>X - Kritische Blutung</legend>
          <div className="xabcde-subgrid">
            {renderXabcdeSelect('blutung', 'Blutung')}
            <label>
              Lokalisation
              <input value={xabcde.blutung_lokalisation || ''} onChange={(event) => updateXabcde('blutung_lokalisation', event.target.value)} />
            </label>
          </div>
        </fieldset>
      );
    }

    if (xabcdeSection === 'A') {
      return (
        <fieldset className="xabcde-panel">
          <legend>A - Airway</legend>
          <div className="xabcde-subgrid">
            {renderXabcdeSelect('atemweg', 'Atemweg')}
            {renderXabcdeSelect('hws', 'HWS')}
          </div>
        </fieldset>
      );
    }

    if (xabcdeSection === 'B') {
      return (
        <fieldset className="xabcde-panel">
          <legend>B - Breathing</legend>
          <div className="xabcde-subgrid">
            {renderXabcdeSelect('atmung', 'Atmung')}
            {renderXabcdeSelect('atemgeraeusche', 'Atemgeräusche')}
            {renderXabcdeSelect('sauerstoff', 'Sauerstoffgabe')}
          </div>
        </fieldset>
      );
    }

    if (xabcdeSection === 'C') {
      return (
        <fieldset className="xabcde-panel">
          <legend>C - Circulation</legend>
          <div className="xabcde-subgrid">
            {renderXabcdeSelect('haut', 'Haut')}
            {renderXabcdeSelect('rekap', 'Rekapillarisierungszeit')}
            {renderXabcdeSelect('pulsqualitaet', 'Pulsqualität')}
          </div>
        </fieldset>
      );
    }

    if (xabcdeSection === 'D') {
      const status = befastStatus();
      return (
        <fieldset className="xabcde-panel">
          <legend>D - Disability</legend>
          <div className="xabcde-subgrid">
            {renderXabcdeSelect('avpu', 'AVPU')}
            {renderXabcdeSelect('pupillen', 'Pupillen')}
          </div>

          {!isChild && <>
          <div className="inline-divider" />
          <h3>BE-FAST Schlaganfall-Screening</h3>
          <p className="field-hint">B Balance · E Eyes · F Face · A Arms · S Speech · T Time</p>
          <div className="xabcde-subgrid">
            {renderXabcdeSelect('befast_balance', 'B - Balance')}
            {renderXabcdeSelect('befast_eyes', 'E - Eyes')}
            {renderXabcdeSelect('befast_face', 'F - Face')}
            {renderXabcdeSelect('befast_arms', 'A - Arms')}
            {renderXabcdeSelect('befast_speech', 'S - Speech')}
            <label>
              T - Time / Symptombeginn
              <input
                value={xabcde.befast_time || ''}
                onChange={(event) => updateXabcde('befast_time', event.target.value)}
                placeholder="z. B. 14:20 Uhr oder zuletzt gesund um 12:00 Uhr"
              />
            </label>
          </div>
          {status && <div className={`befast-status befast-${status.level}`}>{status.text}</div>}
          </>}
        </fieldset>
      );
    }

    return (
      <fieldset className="xabcde-panel">
        <legend>E - Exposure</legend>
        <div className="xabcde-subgrid">
          {renderXabcdeSelect('bodycheck', 'Bodycheck')}
          <div className="xabcde-flags">
            <span>Weitere Befunde</span>
            <label className="checkbox-line">
              <input type="checkbox" checked={Boolean(xabcde.unterkuehlung)} onChange={() => toggleXabcdeFlag('unterkuehlung')} />
              Unterkühlung
            </label>
            <label className="checkbox-line">
              <input type="checkbox" checked={Boolean(xabcde.verbrennung)} onChange={() => toggleXabcdeFlag('verbrennung')} />
              Verbrennung
            </label>
          </div>
        </div>
        {xabcde.bodycheck === 'Auffällig' && (<>
          <label className="wide-field">
            Auffälligkeiten
            <textarea value={xabcde.bodycheck_text || ''} onChange={(event) => updateXabcde('bodycheck_text', event.target.value)} rows={5} />
          </label>
          <section className="trauma-body-map">
            <div className="section-head compact-head"><h3>Trauma-Lokalisation</h3><span>Körperregion anklicken und Befund auswählen</span></div>
            <div className="body-map-grid">{bodyMap('vorne')}{bodyMap('hinten')}</div>
            {traumaFindings().map((finding) => {
              const anatomy = traumaBodyRegions[finding.region] || {};
              const expanded = selectedTraumaRegion === finding.id;
              return <article className={`trauma-finding ${expanded ? 'expanded' : ''}`} key={finding.id}>
                <button type="button" className="trauma-finding-head" onClick={() => setSelectedTraumaRegion(expanded ? '' : finding.id)}><strong>{anatomy.label || finding.region} · {finding.side}</strong><span>{(finding.verletzungsarten || []).join(', ') || 'Befund noch offen'}</span></button>
                {expanded && <div className="trauma-finding-editor">
                  <div className="check-grid">{traumaInjuryTypes.map((type) => <label className="checkbox-line" key={type}><input type="checkbox" checked={(finding.verletzungsarten || []).includes(type)} onChange={() => toggleTraumaInjury(finding.id, type)} />{type}</label>)}</div>
                  <div className="form-grid">
                    <label>Blutungsstärke<select value={finding.blutung || ''} onChange={(event) => updateTraumaFinding(finding.id, 'blutung', event.target.value)}><option value="">Keine Angabe</option><option value="keine">keine</option><option value="gering">gering</option><option value="mittel">mittel</option><option value="stark/kritisch">stark / kritisch</option><option value="kontrolliert">kontrolliert</option></select></label>
                    <label>Zusatzbefund<input value={finding.notiz || ''} onChange={(event) => updateTraumaFinding(finding.id, 'notiz', event.target.value)} /></label>
                  </div>
                  <div className="anatomy-hint"><strong>Anatomische Orientierung</strong><span>Knochen: {anatomy.bones}</span><span>Größere Gefäße in der Region: {anatomy.vessels}</span><small>Nähe bedeutet keine Verletzung. Klinisch untersuchen und gegebenenfalls bildgebend abklären.</small></div>
                  <button type="button" className="remove-trauma-finding" onClick={() => removeTraumaFinding(finding.id)}>Markierung entfernen</button>
                </div>}
              </article>;
            })}
          </section>
        </>)}
      </fieldset>
    );
  }

  function updateSamplers(key, value) {
    setPatient((current) => ({
      ...current,
      samplers: {
        ...(current.samplers || {}),
        [key]: value
      }
    }));
  }

  function toggleSamplerRisk(key) {
    updateSamplers(key, !Boolean(samplers[key]));
  }

  function renderSamplersContent() {
    if (samplersSection === 'S1') {
      return (
        <fieldset className="samplers-panel">
          <legend>S - Symptome</legend>
          <label>
            Beschwerden / Symptome
            <textarea value={samplers.symptome || ''} onChange={(event) => updateSamplers('symptome', event.target.value)} rows={7} />
          </label>
        </fieldset>
      );
    }

    if (samplersSection === 'A') {
      return (
        <fieldset className="samplers-panel">
          <legend>A - Allergien</legend>
          <label>
            Allergien
            <select value={samplers.allergien || 'Keine Angabe'} onChange={(event) => updateSamplers('allergien', event.target.value)}>
              {['Keine Angabe', 'Keine bekannt', 'Vorhanden'].map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          {samplers.allergien === 'Vorhanden' && (
            <label>
              Welche Allergien?
              <input value={samplers.allergien_text || ''} onChange={(event) => updateSamplers('allergien_text', event.target.value)} />
            </label>
          )}
        </fieldset>
      );
    }

    if (samplersSection === 'M') {
      return (
        <fieldset className="samplers-panel">
          <legend>M - Medikamente</legend>
          <label>
            Medikamente
            <select value={samplers.medikamente_option || 'Keine Angabe'} onChange={(event) => updateSamplers('medikamente_option', event.target.value)}>
              {['Keine Angabe', 'Siehe Medikamentenplan', 'Medikamente eingeben'].map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          {samplers.medikamente_option === 'Medikamente eingeben' && (
            <label>
              Bitte Medikamente eingeben
              <textarea value={samplers.medikamente || ''} onChange={(event) => updateSamplers('medikamente', event.target.value)} rows={6} />
            </label>
          )}
        </fieldset>
      );
    }

    if (samplersSection === 'P') {
      return (
        <fieldset className="samplers-panel">
          <legend>P - Patientenvorgeschichte</legend>
          <label>
            Vorerkrankungen
            <textarea value={samplers.vorgeschichte || ''} onChange={(event) => updateSamplers('vorgeschichte', event.target.value)} rows={7} />
          </label>
          {isChild && <div className="form-grid pediatric-history">
            <label>Impfstatus<select value={samplers.impfstatus || ''} onChange={(event) => updateSamplers('impfstatus', event.target.value)}><option value="">Keine Angabe</option><option value="altersentsprechend vollständig">altersentsprechend vollständig</option><option value="unvollständig">unvollständig</option><option value="unbekannt">unbekannt</option></select></label>
            <label>Ausgangszustand / Entwicklung<input value={samplers.ausgangszustand_kind || ''} onChange={(event) => updateSamplers('ausgangszustand_kind', event.target.value)} /></label>
            <label>Geburts-/Frühgeburtsanamnese<input value={samplers.geburtsanamnese || ''} onChange={(event) => updateSamplers('geburtsanamnese', event.target.value)} /></label>
            <label>Betreuungsperson<input value={samplers.betreuungsperson || ''} onChange={(event) => updateSamplers('betreuungsperson', event.target.value)} placeholder="Rolle, keine Klarnamen im Pilotbetrieb" /></label>
          </div>}
        </fieldset>
      );
    }

    if (samplersSection === 'L') {
      return (
        <fieldset className="samplers-panel">
          <legend>L - Letzte Nahrungsaufnahme</legend>
          <label>
            Letzte Mahlzeit
            <select value={samplers.letzte_mahlzeit || 'Keine Angabe'} onChange={(event) => updateSamplers('letzte_mahlzeit', event.target.value)}>
              {['Keine Angabe', '< 2 Stunden', '2-6 Stunden', '> 6 Stunden', 'Unbekannt', 'Eigene Eingabe'].map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          {samplers.letzte_mahlzeit === 'Eigene Eingabe' && (
            <label>
              Eigene Eingabe
              <input value={samplers.letzte_mahlzeit_text || ''} onChange={(event) => updateSamplers('letzte_mahlzeit_text', event.target.value)} />
            </label>
          )}
          <div className="samplers-subgrid">
            {isChild && <label>Trinkmenge / Nahrungsaufnahme<input value={samplers.trinkmenge_kind || ''} onChange={(event) => updateSamplers('trinkmenge_kind', event.target.value)} /></label>}
            {isChild && <label>Nasse Windeln / Ausscheidung<input value={samplers.windeln_kind || ''} onChange={(event) => updateSamplers('windeln_kind', event.target.value)} /></label>}
            {isChild && <label>Fieberdauer<input value={samplers.fieberdauer_kind || ''} onChange={(event) => updateSamplers('fieberdauer_kind', event.target.value)} /></label>}
            {isChild && <label>Exanthem / Krampf / Fremdkörperverdacht<input value={samplers.besonderheiten_kind || ''} onChange={(event) => updateSamplers('besonderheiten_kind', event.target.value)} /></label>}
            <label>
              Letzte Medikamenteneinnahme
              <input value={samplers.letzte_medikamenteneinnahme || ''} onChange={(event) => updateSamplers('letzte_medikamenteneinnahme', event.target.value)} />
            </label>
            <label>
              Letzter Stuhlgang
              <input value={samplers.letzter_stuhlgang || ''} onChange={(event) => updateSamplers('letzter_stuhlgang', event.target.value)} />
            </label>
            <label>
              Letzte Miktion / Wasserlassen
              <input value={samplers.letzte_miktion || ''} onChange={(event) => updateSamplers('letzte_miktion', event.target.value)} />
            </label>
            <label>
              Letztes Erbrechen
              <input value={samplers.letztes_erbrechen || ''} onChange={(event) => updateSamplers('letztes_erbrechen', event.target.value)} />
            </label>
          </div>
        </fieldset>
      );
    }

    if (samplersSection === 'E') {
      return (
        <fieldset className="samplers-panel">
          <legend>E - Ereignis</legend>
          <div className="form-grid trauma-mechanism-grid">
            <label>Unfall-/Traumamechanismus<select value={samplers.trauma_mechanismus || ''} onChange={(event) => updateSamplers('trauma_mechanismus', event.target.value)}><option value="">Kein Trauma / keine Angabe</option><option value="Sturz">Sturz</option><option value="Verkehrsunfall">Verkehrsunfall</option><option value="Anprall/Kollision">Anprall / Kollision</option><option value="Penetrierendes Trauma">Penetrierendes Trauma</option><option value="Quetschung/Einklemmung">Quetschung / Einklemmung</option><option value="Explosion">Explosion</option><option value="Sporttrauma">Sporttrauma</option><option value="Sonstiges Trauma">Sonstiges Trauma</option></select></label>
            {samplers.trauma_mechanismus === 'Sturz' && <label>Sturzhöhe<select value={samplers.sturzhoehe_kategorie || ''} onChange={(event) => updateSamplers('sturzhoehe_kategorie', event.target.value)}><option value="">Bitte auswählen</option><option value="ebenerdig">ebenerdig</option><option value="unter 3 m">unter 3 m</option><option value="3 m oder höher">3 m oder höher</option><option value="unbekannt">unbekannt</option></select></label>}
            {samplers.trauma_mechanismus === 'Sturz' && <label>Geschätzte Höhe<input value={samplers.sturzhoehe_meter || ''} onChange={(event) => updateSamplers('sturzhoehe_meter', event.target.value)} inputMode="decimal" placeholder="Meter, falls bekannt" /></label>}
            <label>Aufprallfläche / Untergrund<input value={samplers.aufprallflaeche || ''} onChange={(event) => updateSamplers('aufprallflaeche', event.target.value)} /></label>
            <label>Aufprallrichtung / Körperposition<input value={samplers.aufprallrichtung || ''} onChange={(event) => updateSamplers('aufprallrichtung', event.target.value)} /></label>
            <label>Schutzsysteme<input value={samplers.schutzsysteme || ''} onChange={(event) => updateSamplers('schutzsysteme', event.target.value)} placeholder="Helm, Gurt, Airbag ..." /></label>
            <label>Einklemmung / Herausschleudern / Überschlag<input value={samplers.trauma_besonderheiten || ''} onChange={(event) => updateSamplers('trauma_besonderheiten', event.target.value)} /></label>
          </div>
          <label>
            Ereignisbeschreibung
            <textarea value={samplers.ereignis || ''} onChange={(event) => updateSamplers('ereignis', event.target.value)} rows={8} />
          </label>
        </fieldset>
      );
    }

    if (samplersSection === 'R') {
      const activeRiskLabels = isChild ? pediatricRiskFactorLabels : riskFactorLabels;
      return (
        <fieldset className="samplers-panel">
          <legend>R - Risikofaktoren</legend>
          <div className="samplers-check-grid">
            {Object.entries(activeRiskLabels).map(([key, label]) => (
              <label key={key} className="checkbox-line">
                <input type="checkbox" checked={Boolean(samplers[key])} onChange={() => toggleSamplerRisk(key)} />
                {label}
              </label>
            ))}
          </div>
          <label>
            Weitere Risikofaktoren
            <input value={samplers.risiken_sonstige || ''} onChange={(event) => updateSamplers('risiken_sonstige', event.target.value)} />
          </label>
        </fieldset>
      );
    }

    return (
      <fieldset className="samplers-panel">
        <legend>S - Schwangerschaft</legend>
        <label>
          Schwangerschaft
          <select value={samplers.schwangerschaft || 'Nicht relevant'} onChange={(event) => updateSamplers('schwangerschaft', event.target.value)}>
            {['Nicht relevant', 'Nein', 'Ja', 'Unbekannt'].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
      </fieldset>
    );
  }

  function updateOpqrst(key, value) {
    setPatient((current) => ({
      ...current,
      opqrst: {
        ...(current.opqrst || {}),
        [key]: value
      }
    }));
  }

  function updatePsyche(key, value) {
    setPatient((current) => ({
      ...current,
      psyche: {
        ...(current.psyche || {}),
        [key]: value
      }
    }));
  }

  function renderOpqrstSelect(key, label) {
    const options = opqrstOptions[key];
    return (
      <label>
        {label}
        <select value={opqrst[key] || options[0]} onChange={(event) => updateOpqrst(key, event.target.value)}>
          {options.map((item) => <option key={item || 'empty'} value={item}>{item || 'Keine Angabe'}</option>)}
        </select>
      </label>
    );
  }

  function opqrstSectionComplete(sectionKey) {
    if (opqrst.schmerz_vorhanden !== 'Ja') return true;
    if (sectionKey === 'O') return hasValue(opqrst.onset) || hasValue(opqrst.onset_text);
    if (sectionKey === 'P') return hasValue(opqrst.provocation) || hasValue(opqrst.provocation_text);
    if (sectionKey === 'Q') return hasValue(opqrst.quality) || hasValue(opqrst.quality_text);
    if (sectionKey === 'R') return hasValue(opqrst.region) || hasValue(opqrst.radiation);
    if (sectionKey === 'S') return hasValue(opqrst.nrs) || hasValue(opqrst.severity_desc);
    if (sectionKey === 'T') return hasValue(opqrst.zeitverlauf) || hasValue(opqrst.dauer);
    return false;
  }

  function renderOpqrstContent() {
    if (opqrst.schmerz_vorhanden !== 'Ja') {
      return (
        <fieldset className="opqrst-panel">
          <legend>Kein Schmerzassessment aktiv</legend>
          <p className="field-hint">Wenn Schmerzen vorhanden sind, öffnet sich hier die strukturierte OPQRST-Erfassung.</p>
        </fieldset>
      );
    }

    if (opqrstSection === 'O') {
      return (
        <fieldset className="opqrst-panel">
          <legend>O - Onset</legend>
          {renderOpqrstSelect('onset', 'Beginn')}
          <label>
            Zusätzliche Information zu Beginn
            <input value={opqrst.onset_text || ''} onChange={(event) => updateOpqrst('onset_text', event.target.value)} />
          </label>
        </fieldset>
      );
    }

    if (opqrstSection === 'P') {
      return (
        <fieldset className="opqrst-panel">
          <legend>P - Provocation/Palliation</legend>
          {renderOpqrstSelect('provocation', 'Was verschlimmert oder lindert den Schmerz?')}
          <label>
            Genauere Beschreibung
            <input value={opqrst.provocation_text || ''} onChange={(event) => updateOpqrst('provocation_text', event.target.value)} />
          </label>
        </fieldset>
      );
    }

    if (opqrstSection === 'Q') {
      return (
        <fieldset className="opqrst-panel">
          <legend>Q - Quality</legend>
          {renderOpqrstSelect('quality', 'Wie beschreibt der Patient den Schmerz?')}
          <label>
            Patienteneigene Beschreibung
            <input value={opqrst.quality_text || ''} onChange={(event) => updateOpqrst('quality_text', event.target.value)} />
          </label>
        </fieldset>
      );
    }

    if (opqrstSection === 'R') {
      return (
        <fieldset className="opqrst-panel">
          <legend>R - Region/Radiation</legend>
          <label>
            Wo tut es weh?
            <input value={opqrst.region || ''} onChange={(event) => updateOpqrst('region', event.target.value)} />
          </label>
          <label>
            Ausstrahlung
            <input value={opqrst.radiation || ''} onChange={(event) => updateOpqrst('radiation', event.target.value)} />
          </label>
        </fieldset>
      );
    }

    if (opqrstSection === 'S') {
      return (
        <fieldset className="opqrst-panel">
          <legend>S - Severity</legend>
          <label>
            Numerische Rating-Skala (NRS) 0-10
            <input
              type="range"
              min="0"
              max="10"
              value={opqrst.nrs ?? 0}
              onChange={(event) => updateOpqrst('nrs', event.target.value)}
            />
            <strong className="range-value">{opqrst.nrs ?? 0}/10</strong>
          </label>
          {renderOpqrstSelect('severity_desc', 'Auswirkung auf Aktivitäten')}
        </fieldset>
      );
    }

    return (
      <fieldset className="opqrst-panel">
        <legend>T - Time</legend>
        {renderOpqrstSelect('zeitverlauf', 'Zeitlicher Verlauf')}
        <label>
          Wie lange besteht der Schmerz bereits?
          <input
            value={opqrst.dauer || ''}
            onChange={(event) => updateOpqrst('dauer', event.target.value)}
            placeholder="z.B. 2 Stunden, seit heute Morgen, ..."
          />
        </label>
      </fieldset>
    );
  }

  function updateAmls(key, value) {
    setPatient((current) => ({
      ...current,
      amls: {
        ...(current.amls || {}),
        [key]: value
      }
    }));
  }

  function addAmlsCandidate() {
    setPatient((current) => ({
      ...current,
      amls: {
        ...(current.amls || {}),
        excluded: Array.isArray((current.amls || {}).excluded) ? (current.amls || {}).excluded : [],
        custom_candidates: [
          ...(Array.isArray((current.amls || {}).custom_candidates) ? (current.amls || {}).custom_candidates : []),
          { diagnose: '', hinweis: '' }
        ]
      }
    }));
  }

  function updateAmlsCandidate(index, key, value) {
    setPatient((current) => {
      const candidates = [...(Array.isArray((current.amls || {}).custom_candidates) ? (current.amls || {}).custom_candidates : [])];
      const existing = candidates[index];
      candidates[index] = typeof existing === 'string' ? { diagnose: existing, [key]: value } : { ...(existing || {}), [key]: value };
      return { ...current, amls: { ...(current.amls || {}), custom_candidates: candidates } };
    });
  }

  function removeAmlsCandidate(index) {
    setPatient((current) => {
      const candidates = [...(Array.isArray((current.amls || {}).custom_candidates) ? (current.amls || {}).custom_candidates : [])];
      candidates.splice(index, 1);
      return { ...current, amls: { ...(current.amls || {}), custom_candidates: candidates } };
    });
  }

  function addAmlsExcluded() {
    setPatient((current) => ({
      ...current,
      amls: {
        ...(current.amls || {}),
        custom_candidates: Array.isArray((current.amls || {}).custom_candidates) ? (current.amls || {}).custom_candidates : [],
        excluded: [
          ...(Array.isArray((current.amls || {}).excluded) ? (current.amls || {}).excluded : []),
          { diagnose: '', begruendung: '' }
        ]
      }
    }));
  }

  function updateAmlsExcluded(index, key, value) {
    setPatient((current) => {
      const excluded = [...(Array.isArray((current.amls || {}).excluded) ? (current.amls || {}).excluded : [])];
      const existing = excluded[index];
      excluded[index] = typeof existing === 'string' ? { diagnose: existing, [key]: value } : { ...(existing || {}), [key]: value };
      return { ...current, amls: { ...(current.amls || {}), excluded } };
    });
  }

  function removeAmlsExcluded(index) {
    setPatient((current) => {
      const excluded = [...(Array.isArray((current.amls || {}).excluded) ? (current.amls || {}).excluded : [])];
      excluded.splice(index, 1);
      return { ...current, amls: { ...(current.amls || {}), excluded } };
    });
  }

  function resetAmlsFunnel() {
    setPatient((current) => ({
      ...current,
      amls: { ...(current.amls || {}), excluded: [], custom_candidates: [], arbeitsdiagnose: '', leitsymptom: '', notizen: '' }
    }));
  }

  function updateUebergabe(key, value) {
    setPatient((current) => ({
      ...current,
      uebergabe: {
        ...(current.uebergabe || {}),
        [key]: value
      }
    }));
  }

  function addUebergabeOption(key, option) {
    if (!option) return;
    setPatient((current) => {
      const currentText = String((current.uebergabe || {})[key] || '');
      const values = currentText
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean);
      const exists = values.some((value) => value.toLowerCase() === option.toLowerCase());
      const nextValues = exists ? values : [...values, option];
      return {
        ...current,
        uebergabe: {
          ...(current.uebergabe || {}),
          [key]: nextValues.join(', ')
        }
      };
    });
  }

  function addMeasure() {
    setPatient((current) => ({
      ...current,
      massnahmen: {
        ...(current.massnahmen || {}),
        timeline: [...((current.massnahmen || {}).timeline || []), { zeit: '', massnahme: '' }],
        medikation: ((current.massnahmen || {}).medikation || [])
      }
    }));
  }

  function updateMeasure(index, key, value) {
    setPatient((current) => {
      const timeline = [...(((current.massnahmen || {}).timeline) || [])];
      timeline[index] = { ...(timeline[index] || {}), [key]: value };
      return {
        ...current,
        massnahmen: {
          ...(current.massnahmen || {}),
          timeline,
          medikation: ((current.massnahmen || {}).medikation || [])
        }
      };
    });
  }

  function removeMeasure(index) {
    setPatient((current) => {
      const timeline = [...(((current.massnahmen || {}).timeline) || [])];
      timeline.splice(index, 1);
      return { ...current, massnahmen: { ...(current.massnahmen || {}), timeline } };
    });
  }

  function addMedication() {
    setPatient((current) => ({
      ...current,
      massnahmen: {
        ...(current.massnahmen || {}),
        timeline: ((current.massnahmen || {}).timeline || []),
        medikation: [...((current.massnahmen || {}).medikation || []), { zeit: '', medikament: '', dosis: '', weg: '' }]
      }
    }));
  }

  function updateMedication(index, key, value) {
    setPatient((current) => {
      const medikation = [...(((current.massnahmen || {}).medikation) || [])];
      medikation[index] = { ...(medikation[index] || {}), [key]: value };
      return {
        ...current,
        massnahmen: {
          ...(current.massnahmen || {}),
          timeline: ((current.massnahmen || {}).timeline || []),
          medikation
        }
      };
    });
  }

  function removeMedication(index) {
    setPatient((current) => {
      const medikation = [...(((current.massnahmen || {}).medikation) || [])];
      medikation.splice(index, 1);
      return { ...current, massnahmen: { ...(current.massnahmen || {}), medikation } };
    });
  }

  function updateReanimation(key, value) {
    setPatient((current) => ({
      ...current,
      reanimation: {
        ...(current.reanimation || {}),
        shocks: Array.isArray((current.reanimation || {}).shocks) ? (current.reanimation || {}).shocks : [],
        [key]: value
      }
    }));
  }

  function addShock() {
    setPatient((current) => ({
      ...current,
      reanimation: {
        ...(current.reanimation || {}),
        shocks: [...(Array.isArray((current.reanimation || {}).shocks) ? (current.reanimation || {}).shocks : []), { zeit: '', energie: '', rhythmus: '' }]
      }
    }));
  }

  function updateShock(index, key, value) {
    setPatient((current) => {
      const shocks = [...(Array.isArray((current.reanimation || {}).shocks) ? (current.reanimation || {}).shocks : [])];
      shocks[index] = { ...(shocks[index] || {}), [key]: value };
      return {
        ...current,
        reanimation: {
          ...(current.reanimation || {}),
          shocks
        }
      };
    });
  }

  function removeShock(index) {
    setPatient((current) => {
      const shocks = [...(Array.isArray((current.reanimation || {}).shocks) ? (current.reanimation || {}).shocks : [])];
      shocks.splice(index, 1);
      return { ...current, reanimation: { ...(current.reanimation || {}), shocks } };
    });
  }

  async function loadAmlsSuggestions() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/protocol/amls-candidates', {
        method: 'POST',
        body: JSON.stringify({ patient })
      }, session.token);
      setAmlsSuggestions(result.candidates || []);
      setStatusText('Differenzialdiagnosen wurden aus Befunden, Vitalwerten und Vorerkrankungen abgeleitet.');
    } catch (err) {
      setError(err.message);
    }
  }

  function applyAmlsSuggestion(item) {
    const name = item?.name || '';
    if (!name) return;
    setPatient((current) => {
      const currentAmls = current.amls || {};
      const candidates = Array.isArray(currentAmls.custom_candidates) ? currentAmls.custom_candidates : [];
      const exists = candidates.some((entry) => (typeof entry === 'string' ? entry : entry?.diagnose || entry?.name) === name);
      return {
        ...current,
        amls: {
          ...currentAmls,
          custom_candidates: exists ? candidates : [...candidates, { diagnose: name, hinweis: item.rationale || item.category || '' }]
        }
      };
    });
    setStatusText(`${name} wurde in die Diagnosehilfe übernommen.`);
  }

  function toggleAmlsExclusion(item) {
    const name = item?.name || '';
    if (!name) return;
    const isExcluded = amlsExcludedNames.has(name);
    if (!isExcluded && amlsRemainingCandidates.length <= 1) {
      setStatusText('Der letzte Kandidat bleibt erhalten. Du kannst ihn als Arbeitsdiagnose übernehmen.');
      return;
    }
    setPatient((current) => {
      const currentAmls = current.amls || {};
      const excluded = Array.isArray(currentAmls.excluded) ? currentAmls.excluded : [];
      const nextExcluded = isExcluded
        ? excluded.filter((entry) => (typeof entry === 'string' ? entry : entry?.diagnose || entry?.name || '') !== name)
        : [...excluded, name];
      return {
        ...current,
        amls: {
          ...currentAmls,
          excluded: nextExcluded,
          arbeitsdiagnose: currentAmls.arbeitsdiagnose === name && !isExcluded ? '' : currentAmls.arbeitsdiagnose
        }
      };
    });
    setStatusText(isExcluded ? `${name} wurde wieder aufgenommen.` : `${name} wurde zurückgestellt.`);
  }

  function adoptAmlsDiagnosis(name) {
    if (!name) return;
    updateAmls('arbeitsdiagnose', name);
    setStatusText(`${name} wurde als Arbeitsdiagnose übernommen.`);
  }

  async function calculateMedication() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/protocol/medication-calculator', {
        method: 'POST',
        body: JSON.stringify({
          sop: calculator.sop,
          age: Number(calculator.age || vitalwerte.alter || 30),
          weight: Number(calculator.weight || 70),
          pregnant: calculator.pregnant,
          inputs: {
            bz: Number(calculator.bz || 55),
            rr_sys: Number(calculator.rr_sys || vitalwerte.rr_sys || 160),
            nrs: Number(calculator.nrs || opqrst.nrs || opqrst.severity || 7)
          }
        })
      }, session.token);
      setCalculatorResult(result);
      setAcceptedCalculatorMedication(null);
      markActionFeedback('calculator-run', 'SOP-Rechner wurde aktualisiert.');
    } catch (err) {
      setError(err.message);
    }
  }

  function addCalculatedMedication(text, index) {
    setPatient((current) => ({
      ...current,
      massnahmen: {
        ...(current.massnahmen || {}),
        timeline: ((current.massnahmen || {}).timeline || []),
        medikation: [...(((current.massnahmen || {}).medikation) || []), { zeit: '', medikament: text, dosis: '', weg: 'laut SOP-Rechner' }]
      }
    }));
    setAcceptedCalculatorMedication({ index, text });
    markActionFeedback(`calculator-med-${index}`, 'Medikation wurde in die Maßnahmen übernommen.');
  }

  async function saveDraft() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/draft', {
        method: 'PUT',
        body: JSON.stringify({ patient })
      }, session.token);
      markActionFeedback('save-draft', `Entwurf gespeichert: ${result.updated_at}`);
      onSync?.(result.updated_at);
      clearLocalDraft(employee?.id);
      setLocalDraft(null);
    } catch (err) {
      clearLocalDraft(employee?.id);
      setLocalDraft(null);
      setError(`${err.message} Keine lokale Sicherung: Patientendaten werden nur verschlüsselt serverseitig gespeichert.`);
    }
  }

  function updateRefusal(key, value) {
    setRefusal((current) => ({ ...current, [key]: value }));
  }

  function markActionFeedback(key, message) {
    setActionFeedback({ key, message });
    setStatusText(message);
    window.setTimeout(() => {
      setActionFeedback((current) => (current?.key === key ? null : current));
    }, 4200);
  }

  function downloadRefusalText() {
    downloadBlob(new Blob([refusalText], { type: 'text/plain;charset=utf-8' }), 'Patientenverweigerung.txt');
    markActionFeedback('refusal-download', 'TXT wurde vorbereitet.');
  }

  function printRefusalText() {
    const opened = printTextDocument('Patientenverweigerung', refusalText);
    markActionFeedback('refusal-print', opened ? 'Druckfenster wurde geöffnet.' : 'Druckfenster konnte nicht geöffnet werden.');
  }

  async function generateProtocol() {
    setError('');
    setProtocolSection('protokoll');

    let localProtocol = '';
    let localError = null;
    try {
      localProtocol = generateLocalProtocolText(patient);
    } catch (err) {
      localError = err;
    }

    if (String(localProtocol || '').trim()) {
      setGeneratedProtocol(localProtocol);
      markActionFeedback('generate-protocol', 'Protokoll wurde erzeugt.');
    } else {
      setGeneratedProtocol('Protokoll wird erstellt...');
      setStatusText('Protokoll wird erstellt...');
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 3500);
    try {
      const result = await api('/api/protocol/preview', {
        method: 'POST',
        body: JSON.stringify({ patient }),
        signal: controller.signal
      }, session.token);
      const protocolText = result.protocol_text || '';
      const nextProtocol = protocolContainsVitalStatuses(protocolText, patient) ? protocolText : localProtocol;
      if (String(nextProtocol || '').trim()) {
        setGeneratedProtocol(nextProtocol);
        markActionFeedback('generate-protocol', nextProtocol === protocolText ? 'Protokoll wurde erzeugt.' : 'Protokoll wurde aus den aktuellen Formularwerten erzeugt.');
      }
    } catch (err) {
      if (localProtocol) {
        setStatusText('Protokoll wurde lokal erzeugt.');
      } else {
        setGeneratedProtocol('');
        setStatusText('');
        setError(localError ? `Lokale Vorschau fehlgeschlagen: ${localError.message || localError}` : err.message);
      }
    } finally {
      window.clearTimeout(timeout);
    }
  }

  async function checkQuality() {
    setError('');
    setStatusText('');
    try {
      const result = await api('/api/protocol/quality', {
        method: 'POST',
        body: JSON.stringify({ patient })
      }, session.token);
      setQualityResult(result);
      setForceFinish(false);
      setProtocolSection('protokoll');
      markActionFeedback('quality-check', `QS geprüft: ${result.score} Punkte.`);
      return result;
    } catch (err) {
      setError(err.message);
      return null;
    }
  }

  async function finishCase() {
    setError('');
    setStatusText('');
    try {
      const quality = qualityResult || await checkQuality();
      if (quality && (quality.warning_count > 0 || quality.critical_count > 0) && !forceFinish) {
        setProtocolSection('protokoll');
        setStatusText('Bitte Warnungen prüfen. Danach kann der Einsatz bewusst mit Warnungen beendet werden.');
        setForceFinish(true);
        return;
      }
      const result = await api('/api/cases/finish', {
        method: 'POST',
        body: JSON.stringify({ patient, force_finish: forceFinish })
      }, session.token);
      setGeneratedProtocol(result.protocol_text || '');
      setQualityResult(result.quality || qualityResult);
      saveLocalShiftCrew(employee?.id, patient.besatzung || {});
      setPatient(patientWithCrewDefaults({}, employee));
      clearLocalDraft(employee?.id);
      setLocalDraft(null);
      setProtocolSection('protokoll');
      setForceFinish(false);
      const warningText = result.quality?.warning_count || result.quality?.critical_count ? ' mit QS-Warnungen' : '';
      markActionFeedback('finish-case', `Einsatz${warningText} beendet und archiviert: ${result.case_id}`);
    } catch (err) {
      setError(err.message);
    }
  }

  async function exportDraftPdf() {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest('/api/protocol/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient })
      }, session.token);
      downloadBlob(file.blob, file.filename);
      markActionFeedback('export-pdf', 'PDF wurde erstellt.');
    } catch (err) {
      setError(err.message);
    }
  }

  async function printDraftPdf() {
    setError('');
    setStatusText('');
    try {
      const file = await fileRequest('/api/protocol/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient })
      }, session.token);
      await api('/api/protocol/print-audit', {
        method: 'POST',
        body: JSON.stringify({ source: 'draft' })
      }, session.token).catch(() => {});
      printBlob(file.blob);
      markActionFeedback('print-pdf', 'Druckfenster wurde geöffnet.');
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className={`app-shell${!standaloneRefusal ? ' protocol-shell' : ''}${protocolNavCollapsed ? ' protocol-nav-collapsed' : ''}`}>
      <header className="topbar">
        <div>
          <div className="app-name">NANA</div>
          <div className="app-subtitle">{standaloneRefusal ? 'Patientenverweigerung' : 'Dokumentation · Vitalwerte & Demographie'}</div>
        </div>
        <div className="user-area">
          <button className="header-button" type="button" onClick={onBack}>
            <Home size={16} /> Hauptmenü
          </button>
          <UserMenu session={session} employee={employee} onLogout={onLogout} />
          <button className="icon-button" onClick={onLogout} aria-label="Abmelden">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      {error && <div className="error-box">{error}</div>}
      {statusText && <div className="success-box">{statusText}</div>}
      {localDraftDecisionPending && localDraft && (
        <section className="offline-draft-box">
          <div>
            <strong>Lokale Sicherung vorhanden</strong>
            <span>{new Date(localDraft.updatedAt).toLocaleString('de-DE')}</span>
          </div>
          <button type="button" onClick={restoreLocalDraft}>Lokalen Entwurf wiederherstellen</button>
          <button type="button" onClick={discardLocalDraft}>Lokalen Entwurf verwerfen</button>
        </section>
      )}

      {!standaloneRefusal && <nav className="protocol-tabs" aria-label="Protokollbereiche">
        <button
          type="button"
          className="protocol-nav-toggle"
          onClick={toggleProtocolNav}
          aria-expanded={!protocolNavCollapsed}
          aria-label={protocolNavCollapsed ? 'Seitennavigation ausklappen' : 'Seitennavigation einklappen'}
          title={protocolNavCollapsed ? 'Navigation ausklappen' : 'Navigation einklappen'}
        >
          {protocolNavCollapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
          <span>Navigation</span>
        </button>
        {protocolNavItems.map((item) => {
          const Icon = item.icon;
          const isActive = protocolSection === item.key;
          return (
            <button
              type="button"
              className={`protocol-nav-item${isActive ? ' active' : ''}${item.complete ? ' complete' : ''}`}
              onClick={() => setProtocolSection(item.key)}
              title={protocolNavCollapsed ? `${item.label}${item.complete ? ' – vollständig' : ''}` : undefined}
              aria-current={isActive ? 'page' : undefined}
              key={item.key}
            >
              <Icon className="protocol-nav-icon" size={19} />
              <span className="protocol-nav-label">{item.label}</span>
              <span className="protocol-nav-status" aria-label={item.complete ? 'Vollständig' : 'Offen'}>
                {item.complete ? <CheckCircle2 size={17} /> : <span />}
              </span>
            </button>
          );
        })}
      </nav>}

      {protocolSection === 'besatzung' && <section className="work-panel crew-box">
        {renderCrewSection()}
      </section>}

      {protocolSection === 'patient' && <section className="work-panel patient-panel">
        <div className="section-head">
          <h2>Patient</h2>
          <span>Patientengruppe und Stammdaten</span>
        </div>

        <div className="patient-type-grid" role="group" aria-label="Patientengruppe">
          <button
            type="button"
            className={patientData.patientengruppe === 'Erwachsen' ? 'selected' : ''}
            onClick={() => selectPatientGroup('Erwachsen')}
          >
            <strong>Erwachsen</strong>
            <span>ab 18 Jahren</span>
          </button>
          <button
            type="button"
            className={patientData.patientengruppe === 'Kind' ? 'selected' : ''}
            onClick={() => selectPatientGroup('Kind')}
          >
            <strong>Kind</strong>
            <span>unter 18 Jahren</span>
          </button>
        </div>

        {isChild && <section className="pediatric-intake">
          <div className="section-head compact-head">
            <h3>Pädiatrischer Modus</h3>
            <span>{pediatricAgeGroup || 'Alter noch offen'}</span>
          </div>
          <div className="age-entry-grid">
            <label>Alter<input value={patientData.alter_wert || ''} onChange={(event) => updatePatientData('alter_wert', event.target.value)} inputMode="numeric" min="0" placeholder="z. B. 8" /></label>
            <label>
              Einheit
              <select value={patientData.alter_einheit || 'Jahre'} onChange={(event) => updatePatientData('alter_einheit', event.target.value)}>
                <option value="Monate">Monate</option>
                <option value="Jahre">Jahre</option>
              </select>
            </label>
          </div>
          <div className="age-entry-grid pediatric-medical-data">
            <label>
              Medizinisches Gewicht
              <input value={patientData.medizinisches_gewicht || ''} onChange={(event) => updatePatientData('medizinisches_gewicht', event.target.value)} inputMode="decimal" placeholder="kg" />
            </label>
            <label>
              Herkunft des Gewichts
              <select value={patientData.gewicht_quelle || ''} onChange={(event) => updatePatientData('gewicht_quelle', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="gemessen">gemessen</option>
                <option value="Elternangabe">von Eltern angegeben</option>
                <option value="geschätzt">geschätzt</option>
                <option value="unbekannt">unbekannt</option>
              </select>
            </label>
          </div>
          <fieldset className="pediatric-assessment">
            <legend>Pädiatrisches Beurteilungsdreieck (PAT)</legend>
            <div className="form-grid">
              {[
                ['erscheinungsbild', 'Erscheinungsbild'],
                ['atemarbeit', 'Atemarbeit'],
                ['hautdurchblutung', 'Hautdurchblutung']
              ].map(([key, label]) => (
                <label key={key}>
                  {label}
                  <select value={patientData.pat?.[key] || ''} onChange={(event) => updatePediatricGroup('pat', key, event.target.value)}>
                    <option value="">Bitte beurteilen</option>
                    <option value="unauffällig">unauffällig</option>
                    <option value="auffällig">auffällig</option>
                  </select>
                </label>
              ))}
            </div>
            <label className="wide-field">PAT-Beobachtung<textarea value={patientData.pat?.notiz || ''} onChange={(event) => updatePediatricGroup('pat', 'notiz', event.target.value)} rows={3} /></label>
            <div className="check-grid pediatric-observations">
              {[
                ['tonus', 'Tonus auffällig'], ['interaktion', 'Interaktion auffällig'], ['troestbarkeit', 'nicht tröstbar'],
                ['blickkontakt', 'Blickkontakt auffällig'], ['einziehungen', 'Einziehungen'], ['nasenfluegeln', 'Nasenflügeln'],
                ['stridor', 'Stridor'], ['stoenen', 'Stöhnen'], ['blass', 'Blässe'], ['marmoriert', 'Marmorierung'], ['zyanose', 'Zyanose']
              ].map(([key, label]) => (
                <label key={key} className="checkbox-line">
                  <input type="checkbox" checked={Boolean(patientData.pat?.[key])} onChange={(event) => updatePediatricGroup('pat', key, event.target.checked)} />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
        </section>}

        <div className="pilot-privacy-note">
          <strong>Pilotbetrieb – keine echten personenbezogenen Daten eingeben</strong>
          <span>Datenschutzrechtlich relevante Stammdaten sind deshalb sichtbar, aber noch deaktiviert.</span>
        </div>

        <fieldset className="privacy-fields" disabled>
          <legend>Patientendaten – im Pilotbetrieb gesperrt</legend>
          <div className="form-grid">
            <label>Vorname<input placeholder="Noch nicht dokumentierbar" /></label>
            <label>Nachname<input placeholder="Noch nicht dokumentierbar" /></label>
            <label>Geburtsdatum<input type="date" /></label>
            {!isChild && <label>Alter<input inputMode="numeric" placeholder="Noch nicht dokumentierbar" /></label>}
            <label>
              Geschlecht
              <select defaultValue="">
                <option value="">Noch nicht dokumentierbar</option>
                <option value="männlich">männlich</option>
                <option value="weiblich">weiblich</option>
                <option value="divers">divers</option>
              </select>
            </label>
            <label className="full-span">Straße und Hausnummer<input placeholder="Noch nicht dokumentierbar" /></label>
            <label>Postleitzahl<input placeholder="Noch nicht dokumentierbar" /></label>
            <label>Wohnort<input placeholder="Noch nicht dokumentierbar" /></label>
            <label>Krankenkasse<input placeholder="Noch nicht dokumentierbar" /></label>
            <label>Versichertennummer<input placeholder="Noch nicht dokumentierbar" /></label>
            <label>Telefonnummer<input placeholder="Noch nicht dokumentierbar" /></label>
            <label>Kontaktperson / Angehörige<input placeholder="Noch nicht dokumentierbar" /></label>
          </div>
        </fieldset>
      </section>}

      {protocolSection === 'vitalwerte' && <section className="work-panel">
        <div className="section-head">
          <h2>Vitalwerte</h2>
          <span>Entwurf pro Mitarbeiter</span>
        </div>

        {isChild && <div className="pediatric-vital-note">
          <strong>{pediatricAgeGroup || 'Pädiatrischer Fall'}: altersbezogene Bewertung erforderlich</strong>
          <span>Puls, Atemfrequenz und Blutdruck werden bis zur fachlichen Freigabe einer Referenztabelle neutral dokumentiert und nicht mit Erwachsenen-Grenzwerten bewertet.</span>
        </div>}

        <div className="form-grid">
          {renderBloodPressurePair()}
          {renderVitalPair({ title: 'Puls', valueKey: 'puls', statusKey: 'puls_status', placeholder: '/min' })}
          {renderVitalPair({ title: 'SpO2', valueKey: 'spo2', statusKey: 'spo2_status', placeholder: '%' })}
          {renderVitalPair({ title: 'Atemfrequenz', valueKey: 'af', statusKey: 'af_status', placeholder: '/min' })}
          {renderVitalPair({ title: 'BZ', valueKey: 'bz', statusKey: 'bz_status', placeholder: 'mg/dL' })}
          {renderVitalPair({ title: 'Temperatur', valueKey: 'temperatur', statusKey: 'temperatur_status', inputMode: 'decimal', placeholder: '°C' })}
          {!isChild && renderVitalPair({ title: 'GCS', valueKey: 'gcs', statusKey: 'gcs_status', placeholder: '/15' })}
        </div>

        {isChild && <fieldset className="pediatric-assessment">
          <legend>Neurologische Beurteilung Kind</legend>
          <div className="form-grid">
            {Object.entries(pediatricGcsOptions).map(([key, options]) => (
              <label key={key}>
                {key === 'gcs_augen' ? 'Augen' : key === 'gcs_verbal' ? 'Verbal, altersadaptiert' : 'Motorisch'}
                <select value={patientData.paediatrie?.[key] || ''} onChange={(event) => updatePediatricGroup('paediatrie', key, event.target.value)}>
                  {options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
            ))}
          </div>
          <div className={`score-result ${pediatricGcsComplete ? '' : 'incomplete'}`}>Kinder-GCS: {pediatricGcsComplete ? `${pediatricGcsTotal}/15` : 'noch unvollständig'}</div>
          <p className="field-hint">Verbale und motorische Reaktion alters- und entwicklungsbezogen beurteilen.</p>
        </fieldset>}

        {isChild && isNewborn && <fieldset className="pediatric-assessment">
          <legend>APGAR – nur Neugeborenenversorgung</legend>
          {['1', '5', '10'].map((minute) => <div className="apgar-block" key={minute}>
            <h4>{minute}. Minute · Summe {apgarTotal(minute) ?? 'offen'}/10</h4>
            <div className="form-grid">
              {apgarComponents.map(([key, label, options]) => <label key={key}>{label}<select value={patientData.paediatrie?.apgar_details?.[minute]?.[key] ?? ''} onChange={(event) => updateApgar(minute, key, event.target.value)}><option value="">Bitte auswählen</option>{options.map((text, score) => <option key={score} value={String(score)}>{text}</option>)}</select></label>)}
            </div>
          </div>)}
          <p className="field-hint">Reanimationsmaßnahmen niemals zur Erhebung des Scores verzögern.</p>
        </fieldset>}

        <label className="wide-field">
          Kurzbericht
          <textarea value={vitalwerte.kurzbericht || ''} onChange={(event) => updateVital('kurzbericht', event.target.value)} rows={5} />
        </label>
      </section>}

      {protocolSection === 'xabcde' && <section className="work-panel">
        <div className="section-head">
          <h2>xABCDE Erstbeurteilung</h2>
          <span>strukturiert nach Priorität</span>
        </div>

        <div className="xabcde-layout">
          <div className="xabcde-nav" role="tablist" aria-label="xABCDE Unterpunkte">
            {xabcdeSections.map((section) => {
              const incomplete = !xabcdeSectionComplete(section.key);
              return (
                <button
                  key={section.key}
                  type="button"
                  className={`${xabcdeSection === section.key ? 'active' : ''} ${incomplete ? 'incomplete' : 'complete'}`}
                  onClick={() => setXabcdeSection(section.key)}
                  title={section.title}
                >
                  {incomplete ? `${section.label} !` : section.label}
                </button>
              );
            })}
          </div>

          <div className="xabcde-active-hint">
            {xabcdeCompletedCount}/{xabcdeSections.length} abgeschlossen · offen: {xabcdeOpenSections.length ? xabcdeOpenSections.join(', ') : 'keine'}
          </div>

          {renderXabcdeContent()}

          <aside className="xabcde-summary">
            <h3>Live-Zusammenfassung</h3>
            <div className="summary-meter"><span style={{ width: `${Math.round((xabcdeCompletedCount / xabcdeSections.length) * 100)}%` }} /></div>
            <p>{hasValue(xabcde.blutung) ? `X: ${xabcde.blutung}` : 'X noch offen'}</p>
            <p>{hasValue(xabcde.atemweg) ? `A: ${xabcde.atemweg}` : 'A noch offen'}</p>
            <p>{hasValue(xabcde.atmung) ? `B: ${xabcde.atmung}` : 'B noch offen'}</p>
            <p>{hasValue(xabcde.haut) ? `C: ${xabcde.haut}` : 'C noch offen'}</p>
            <p>{hasValue(xabcde.avpu) ? `D: AVPU ${xabcde.avpu}` : 'D noch offen'}</p>
            <p>{hasValue(xabcde.bodycheck) ? `E: ${xabcde.bodycheck}` : 'E noch offen'}</p>
          </aside>
        </div>
      </section>}

      {protocolSection === 'samplers' && <section className="work-panel">
        <div className="section-head">
          <h2>SAMPLERS Anamnese</h2>
          <span>strukturierte Patientenbefragung</span>
        </div>

        <div className="samplers-layout">
          <div className="samplers-nav" role="tablist" aria-label="SAMPLERS Unterpunkte">
            {activeSamplersSections.map((section) => (
              <button
                key={section.key}
                type="button"
                className={`${samplersSection === section.key ? 'active' : ''} ${samplersSectionComplete(section.key) ? 'complete' : 'incomplete'}`}
                onClick={() => setSamplersSection(section.key)}
                title={section.title}
              >
                {samplersSectionComplete(section.key) ? section.label : `${section.label} !`}
              </button>
            ))}
          </div>

          <div className="samplers-active-hint">
            {samplersCompletedCount}/{activeSamplersSections.length} Bereiche dokumentiert · offen: {samplersOpenSections.length ? samplersOpenSections.join(', ') : 'keine'}
          </div>

          {renderSamplersContent()}

          <aside className="samplers-summary">
            <h3>Live-Zusammenfassung</h3>
            <div className="summary-meter"><span style={{ width: `${Math.round((samplersCompletedCount / activeSamplersSections.length) * 100)}%` }} /></div>
            <p>{hasValue(samplers.symptome) ? `Symptome: ${samplers.symptome}` : 'Symptome noch offen'}</p>
            <p>{hasValue(formatSelectedAllergies(samplers)) ? `Allergien: ${formatSelectedAllergies(samplers)}` : 'Allergien noch offen'}</p>
            <p>{hasValue(samplers.vorgeschichte) ? `Vorgeschichte: ${samplers.vorgeschichte}` : 'Vorgeschichte noch offen'}</p>
            <p>{hasValue(formatLastMeal(samplers)) ? `Letzte Mahlzeit: ${formatLastMeal(samplers)}` : 'Letzte Mahlzeit noch offen'}</p>
            <p>{hasValue(samplers.ereignis) ? `Ereignis: ${samplers.ereignis}` : 'Ereignis noch offen'}</p>
          </aside>
        </div>
      </section>}

      {protocolSection === 'opqrst' && <section className="work-panel">
        <div className="section-head">
          <h2>OPQRST</h2>
          <span>Schmerz und Leitsymptom</span>
        </div>
        <div className="opqrst-layout">
          <fieldset className="opqrst-pain-toggle">
            <legend>Schmerzassessment</legend>
            <label>
              Schmerzen vorhanden?
              <select value={opqrst.schmerz_vorhanden || 'Nein'} onChange={(event) => updateOpqrst('schmerz_vorhanden', event.target.value)}>
                <option value="Nein">Nein</option>
                <option value="Ja">Ja</option>
              </select>
            </label>
          </fieldset>

          {opqrst.schmerz_vorhanden === 'Ja' && (
            <>
              <div className="opqrst-nav" role="tablist" aria-label="OPQRST Unterpunkte">
                {opqrstSections.map((section) => {
                  const incomplete = !opqrstSectionComplete(section.key);
                  return (
                    <button
                      key={section.key}
                      type="button"
                      className={opqrstSection === section.key ? 'active' : ''}
                      onClick={() => setOpqrstSection(section.key)}
                      title={section.title}
                    >
                      {incomplete ? `${section.label} !` : section.label}
                    </button>
                  );
                })}
              </div>
              <div className="opqrst-active-hint">
                Aktive OPQRST-Sektion: {opqrstSection} · offene Reiter sind mit ! markiert.
              </div>
            </>
          )}

          {renderOpqrstContent()}

          <aside className="opqrst-summary">
            <h3>Live-Zusammenfassung</h3>
            <p>{`Schmerz: ${opqrst.schmerz_vorhanden || 'Nein'}`}</p>
            <p>{hasValue(opqrst.onset) ? `Onset: ${opqrst.onset}` : 'Onset noch offen'}</p>
            <p>{hasValue(opqrst.provocation) ? `Provocation: ${opqrst.provocation}` : 'Provocation noch offen'}</p>
            <p>{hasValue(opqrst.quality) ? `Quality: ${opqrst.quality}` : 'Quality noch offen'}</p>
            <p>{hasValue(opqrst.region) ? `Region: ${opqrst.region}` : 'Region noch offen'}</p>
            <p>{hasValue(opqrst.nrs) ? `NRS: ${opqrst.nrs}/10` : 'NRS noch offen'}</p>
          </aside>
        </div>
      </section>}

      {protocolSection === 'amls' && <section className="work-panel">
        <div className="section-head">
          <h2>Diagnosehilfe</h2>
          <span>Aus Vitalwerten, Anamnese und Vorerkrankungen abgeleitete Differenzialdiagnosen</span>
        </div>

        <div className="pilot-privacy-note diagnosis-safety-note">
          <strong>Dokumentations- und Denkhilfe</strong>
          <span>Die Vorschläge stellen keine Diagnose und ersetzen weder Untersuchung, Leitlinie, SOP noch ärztliche Beurteilung. Gelb bedeutet: Mindestens ein dokumentierter Befund passt derzeit nicht.</span>
        </div>

        <div className="amls-summary">
          <div>
            <strong>{amlsVisibleCandidates.length}</strong>
            <span>Kandidaten</span>
          </div>
          <div>
            <strong>{amlsExcluded.length}</strong>
            <span>zurückgestellt</span>
          </div>
          <div>
            <strong>{amlsRemainingCandidates.length}</strong>
            <span>verbleibend</span>
          </div>
        </div>
        <div className={`amls-readiness amls-readiness-${amlsReadiness.level}`}>
          <CheckCircle2 size={18} />
          <span>{amlsReadiness.text}</span>
        </div>
        <div className="amls-funnel">
          <div>Diagnoseübersicht · {amlsVisibleCandidates.length} Kandidaten · passend {amlsMatchingCount} · gelb prüfen {amlsCheckCount} · zurückgestellt {amlsExcluded.length}</div>
          <span />
          <strong>{amlsRemainingCandidates.length} verbleibend</strong>
        </div>

        <div className="assessment-grid">
          <fieldset>
            <legend>Verdacht</legend>
            <label>
              Leitsymptom / Hauptproblem
              <input value={amls.leitsymptom || ''} onChange={(event) => updateAmls('leitsymptom', event.target.value)} />
            </label>
            <label>
              Arbeitsdiagnose
              <input value={amls.arbeitsdiagnose || ''} onChange={(event) => updateAmls('arbeitsdiagnose', event.target.value)} />
            </label>
          </fieldset>
          <fieldset>
            <legend>Begründung</legend>
            <label>
              Klinische Notiz / Entscheidungsgrundlage
              <textarea value={amls.notizen || ''} onChange={(event) => updateAmls('notizen', event.target.value)} rows={6} />
            </label>
          </fieldset>
        </div>

        <div className="list-head">
          <h3>Differenzialdiagnosen</h3>
          <div className="list-actions">
            <button type="button" onClick={loadAmlsSuggestions}>Diagnosehilfe aktualisieren</button>
            <button type="button" onClick={addAmlsCandidate}>Kandidat hinzufügen</button>
          </div>
        </div>
        <div className="candidate-grid amls-candidate-grid">
          {amlsVisibleCandidates.map((item) => {
            const isExcluded = amlsExcludedNames.has(item.name);
            const conflicts = item.conflicts || [];
            const statusClass = isExcluded ? 'excluded' : conflicts.length ? 'check' : 'matching';
            return (
              <button
                type="button"
                className={`amls-candidate-card amls-${statusClass}`}
                key={`${item.category}-${item.name}`}
                onClick={() => toggleAmlsExclusion(item)}
              >
                <strong>{isExcluded ? `Zurückgestellt: ${item.name}` : item.name}</strong>
                <span>{item.category} · {item.rationale}</span>
                {conflicts.length > 0 && !isExcluded && <small>Prüfen: {conflicts.join(' · ')}</small>}
              </button>
            );
          })}
          {amlsVisibleCandidates.length === 0 && <p className="muted">Noch keine Kandidaten. Diagnosehilfe aktualisieren oder eigene Diagnosen ergänzen.</p>}
        </div>
        {amlsRemainingCandidates.length === 1 && (
          <div className="amls-final">
            <strong>Letzter verbleibender Kandidat: {amlsRemainingCandidates[0].name}</strong>
            <button type="button" onClick={() => adoptAmlsDiagnosis(amlsRemainingCandidates[0].name)}>
              Als Arbeitsdiagnose übernehmen
            </button>
          </div>
        )}
        <div className="dynamic-list">
          {amlsCandidates.map((item, index) => {
            const candidate = typeof item === 'string' ? { diagnose: item, hinweis: '' } : item || {};
            return (
              <div className="dynamic-row amls-row" key={`amls-candidate-${index}`}>
                <input
                  placeholder="Diagnose / Verdacht"
                  value={candidate.diagnose || candidate.name || ''}
                  onChange={(event) => updateAmlsCandidate(index, 'diagnose', event.target.value)}
                />
                <input
                  placeholder="Hinweis, Befund oder warum möglich"
                  value={candidate.hinweis || candidate.rationale || ''}
                  onChange={(event) => updateAmlsCandidate(index, 'hinweis', event.target.value)}
                />
                <button type="button" onClick={() => removeAmlsCandidate(index)}>Entfernen</button>
              </div>
            );
          })}
          {amlsCandidates.length === 0 && <p className="muted">Noch keine Differenzialdiagnosen ergänzt.</p>}
        </div>

        <div className="list-head">
          <h3>Ausschlüsse / zurückgestellt</h3>
          <button type="button" onClick={addAmlsExcluded}>Ausschluss hinzufügen</button>
        </div>
        <div className="dynamic-list">
          {amlsExcluded.map((item, index) => {
            const excluded = typeof item === 'string' ? { diagnose: item, begruendung: '' } : item || {};
            return (
              <div className="dynamic-row amls-row" key={`amls-excluded-${index}`}>
                <input
                  placeholder="Diagnose"
                  value={excluded.diagnose || excluded.name || ''}
                  onChange={(event) => updateAmlsExcluded(index, 'diagnose', event.target.value)}
                />
                <input
                  placeholder="Begründung"
                  value={excluded.begruendung || excluded.rationale || ''}
                  onChange={(event) => updateAmlsExcluded(index, 'begruendung', event.target.value)}
                />
                <button type="button" onClick={() => removeAmlsExcluded(index)}>Entfernen</button>
              </div>
            );
          })}
          {amlsExcluded.length === 0 && <p className="muted">Noch keine Ausschlüsse dokumentiert.</p>}
        </div>

        <div className="protocol-toolbar amls-actions">
          <button type="button" onClick={resetAmlsFunnel}><RotateCcw size={16} /> Diagnosehilfe zurücksetzen</button>
          <button type="button" onClick={generateProtocol}>Protokoll mit Diagnosehilfe generieren</button>
        </div>
      </section>}

      {protocolSection === 'psyche' && <section className="work-panel psyche-panel">
        <div className="section-head">
          <h2>Psyche</h2>
          <span>Psychischer Zustand · Gefährdung · PsychKG NRW</span>
        </div>

        <div className="psyche-legal-note">
          <Brain size={20} />
          <div>
            <strong>Dokumentationshilfe – keine eigenständige Unterbringungsanordnung</strong>
            <span>Konkrete Beobachtungen festhalten. Eine Unterbringung nach PsychKG NRW wird durch Ordnungsbehörde beziehungsweise Amtsgericht veranlasst; bei Gefahr im Verzug gelten die Voraussetzungen des § 14 PsychKG NRW.</span>
            <div className="psyche-legal-actions" aria-label="Originalparagraphen PsychKG NRW">
              <a
                href="https://recht.nrw.de/lrgv/gesetz/01072025-gesetz-ueber-hilfen-und-schutzmassnahmen-bei-psychischen-krankheiten-psychkg/#:~:text=%C2%A7%2014%20Sofortige%20Unterbringung"
                target="_blank"
                rel="noreferrer"
              >
                § 14 Sofortige Unterbringung <ExternalLink size={14} />
              </a>
              <a
                href="https://recht.nrw.de/lrgv/gesetz/01072025-gesetz-ueber-hilfen-und-schutzmassnahmen-bei-psychischen-krankheiten-psychkg/#:~:text=%C2%A7%2026%20Freiwilliger%20Krankenhausaufenthalt"
                target="_blank"
                rel="noreferrer"
              >
                § 26 Freiwilliger Krankenhausaufenthalt <ExternalLink size={14} />
              </a>
            </div>
          </div>
        </div>

        <fieldset>
          <legend>Psychischer Befund</legend>
          <div className="form-grid">
            <label>
              Psychischer Zustand
              <select value={psyche.zustand || ''} onChange={(event) => updatePsyche('zustand', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="unauffällig">unauffällig</option>
                <option value="ängstlich / angespannt">ängstlich / angespannt</option>
                <option value="depressiv">depressiv</option>
                <option value="manisch / enthemmt">manisch / enthemmt</option>
                <option value="psychotisch / wahnhaft">psychotisch / wahnhaft</option>
                <option value="agitiert / aggressiv">agitiert / aggressiv</option>
                <option value="intoxikiert / substanzbeeinflusst">intoxikiert / substanzbeeinflusst</option>
                <option value="desorientiert / verwirrt">desorientiert / verwirrt</option>
                <option value="sonstiger auffälliger Zustand">sonstiger auffälliger Zustand</option>
              </select>
            </label>
            <label>
              Orientierung
              <select value={psyche.orientierung || ''} onChange={(event) => updatePsyche('orientierung', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="voll orientiert">voll orientiert</option>
                <option value="teilweise desorientiert">teilweise desorientiert</option>
                <option value="nicht orientiert">nicht orientiert</option>
                <option value="nicht sicher beurteilbar">nicht sicher beurteilbar</option>
              </select>
            </label>
            <label>
              Verhalten / Kooperation
              <select value={psyche.kooperation || ''} onChange={(event) => updatePsyche('kooperation', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="kooperativ">kooperativ</option>
                <option value="eingeschränkt kooperativ">eingeschränkt kooperativ</option>
                <option value="nicht kooperativ">nicht kooperativ</option>
                <option value="wechselnd">wechselnd</option>
                <option value="nicht beurteilbar">nicht beurteilbar</option>
              </select>
            </label>
            <label>
              Einwilligungsfähigkeit
              <select value={psyche.einwilligungsfaehigkeit || ''} onChange={(event) => updatePsyche('einwilligungsfaehigkeit', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="gegeben eingeschätzt">gegeben eingeschätzt</option>
                <option value="nicht gegeben eingeschätzt">nicht gegeben eingeschätzt</option>
                <option value="zweifelhaft / ärztlich zu klären">zweifelhaft / ärztlich zu klären</option>
                <option value="nicht beurteilbar">nicht beurteilbar</option>
              </select>
            </label>
          </div>
          <label className="wide-field">
            Konkrete Beobachtungen / psychopathologischer Kurzbefund
            <textarea value={psyche.begruendung || ''} onChange={(event) => updatePsyche('begruendung', event.target.value)} rows={4} placeholder="Beobachtbares Verhalten, Äußerungen, Affekt, Wahrnehmung, Anlass und zeitlicher Verlauf sachlich dokumentieren" />
          </label>
        </fieldset>

        <fieldset>
          <legend>Gefährdungsbeurteilung</legend>
          <div className="form-grid">
            <label>
              Suizidalität
              <select value={psyche.suizidalitaet || ''} onChange={(event) => updatePsyche('suizidalitaet', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="verneint / keine Hinweise">verneint / keine Hinweise</option>
                <option value="passive Todeswünsche">passive Todeswünsche</option>
                <option value="Suizidgedanken ohne konkreten Plan">Suizidgedanken ohne konkreten Plan</option>
                <option value="konkreter Plan / Vorbereitung">konkreter Plan / Vorbereitung</option>
                <option value="Suizidversuch erfolgt">Suizidversuch erfolgt</option>
                <option value="nicht sicher beurteilbar">nicht sicher beurteilbar</option>
              </select>
            </label>
            <label>
              Eigengefährdung
              <select value={psyche.eigengefaehrdung || ''} onChange={(event) => updatePsyche('eigengefaehrdung', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="keine Hinweise">keine Hinweise</option>
                <option value="möglich">möglich</option>
                <option value="gegenwärtig erheblich">gegenwärtig erheblich</option>
                <option value="nicht sicher beurteilbar">nicht sicher beurteilbar</option>
              </select>
            </label>
            <label>
              Fremdgefährdung
              <select value={psyche.fremdgefaehrdung || ''} onChange={(event) => updatePsyche('fremdgefaehrdung', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="keine Hinweise">keine Hinweise</option>
                <option value="möglich">möglich</option>
                <option value="gegenwärtig erhebliche Gefährdung bedeutender Rechtsgüter anderer">gegenwärtig erhebliche Gefährdung bedeutender Rechtsgüter anderer</option>
                <option value="nicht sicher beurteilbar">nicht sicher beurteilbar</option>
              </select>
            </label>
          </div>
        </fieldset>

        <fieldset>
          <legend>Aufnahme / Unterbringung</legend>
          <div className="form-grid">
            <label className="full-span">
              Dokumentierter Aufnahme- oder Unterbringungsweg
              <select value={psyche.unterbringungsweg || ''} onChange={(event) => updatePsyche('unterbringungsweg', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="Keine psychiatrische Einweisung / Unterbringung">Keine psychiatrische Einweisung / Unterbringung</option>
                <option value="Freiwilliger Krankenhausaufenthalt (§ 26 PsychKG NRW)">Freiwilliger Krankenhausaufenthalt (§ 26 PsychKG NRW)</option>
                <option value="Unterbringung auf Antrag der Ordnungsbehörde (§§ 10–12 PsychKG NRW)">Unterbringung auf Antrag der Ordnungsbehörde (§§ 10–12 PsychKG NRW)</option>
                <option value="Sofortige Unterbringung bei Gefahr im Verzug (§ 14 PsychKG NRW)">Sofortige Unterbringung bei Gefahr im Verzug (§ 14 PsychKG NRW)</option>
                <option value="Gerichtlich angeordnete Unterbringung (§§ 12–13 PsychKG NRW)">Gerichtlich angeordnete Unterbringung (§§ 12–13 PsychKG NRW)</option>
                <option value="Anderer Rechtsweg / Grundlage">Anderer Rechtsweg / Grundlage</option>
              </select>
            </label>
            <label>
              Veranlasst durch
              <select value={psyche.veranlasst_durch || ''} onChange={(event) => updatePsyche('veranlasst_durch', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="Patient/in selbst">Patient/in selbst</option>
                <option value="Notarzt / Ärztin / Arzt">Notarzt / Ärztin / Arzt</option>
                <option value="Ordnungsbehörde">Ordnungsbehörde</option>
                <option value="Amtsgericht">Amtsgericht</option>
                <option value="Polizei in Amtshilfe">Polizei in Amtshilfe</option>
                <option value="nicht bekannt">nicht bekannt</option>
              </select>
            </label>
            <label>
              Ärztliches Zeugnis / Beschluss
              <select value={psyche.nachweis || ''} onChange={(event) => updatePsyche('nachweis', event.target.value)}>
                <option value="">Bitte auswählen</option>
                <option value="liegt vor">liegt vor</option>
                <option value="angekündigt / in Erstellung">angekündigt / in Erstellung</option>
                <option value="liegt nicht vor">liegt nicht vor</option>
                <option value="nicht geprüft / nicht bekannt">nicht geprüft / nicht bekannt</option>
                <option value="bei freiwilliger Aufnahme nicht erforderlich">bei freiwilliger Aufnahme nicht erforderlich</option>
              </select>
            </label>
            <label>
              Zielklinik
              <input value={psyche.zielklinik || ''} onChange={(event) => updatePsyche('zielklinik', event.target.value)} placeholder="Klinik / Fachabteilung" />
            </label>
            <label>
              Begleitung / Sicherung
              <input value={psyche.begleitung || ''} onChange={(event) => updatePsyche('begleitung', event.target.value)} placeholder="z. B. Ordnungsamt, Polizei, Notarzt" />
            </label>
            <label className="full-span">
              Weitere Notizen
              <textarea value={psyche.notizen || ''} onChange={(event) => updatePsyche('notizen', event.target.value)} rows={3} />
            </label>
          </div>
        </fieldset>
      </section>}

      {protocolSection === 'rechner' && <section className="work-panel">
        <div className="section-head">
          <h2>Medikamentenrechner</h2>
          <span>SOP-Unterstützung</span>
        </div>
        <div className="form-grid">
          <label>
            SOP
            <select value={calculator.sop} onChange={(event) => setCalculator({ ...calculator, sop: event.target.value })}>
              {[
                'Anaphylaxie (SOPKB0105)',
                'Asthma/COPD Bronchialobstruktion (SOPKB0207)',
                'Hypoglykämie',
                'Krampfanfall',
                'Schlaganfall',
                'Kardiales Lungenödem',
                'Starke Schmerzen',
                'Hypertensiver Notfall',
                'Nichttraumatischer Brustschmerz: ACS',
                'Abdominelle Schmerzen / Koliken',
                'Lungenarterienembolie'
              ].map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            Alter
            <input value={calculator.age} onChange={(event) => setCalculator({ ...calculator, age: event.target.value })} inputMode="numeric" />
          </label>
          <label>
            Gewicht kg
            <input value={calculator.weight} onChange={(event) => setCalculator({ ...calculator, weight: event.target.value })} inputMode="decimal" />
          </label>
          <label>
            Schwangerschaft
            <select value={calculator.pregnant} onChange={(event) => setCalculator({ ...calculator, pregnant: event.target.value })}>
              <option value="Nein">Nein</option>
              <option value="Ja">Ja</option>
              <option value="Unbekannt">Unbekannt</option>
            </select>
          </label>
          <label>
            BZ mg/dl
            <input value={calculator.bz} onChange={(event) => setCalculator({ ...calculator, bz: event.target.value })} inputMode="numeric" />
          </label>
          <label>
            RR syst.
            <input value={calculator.rr_sys} onChange={(event) => setCalculator({ ...calculator, rr_sys: event.target.value })} inputMode="numeric" />
          </label>
          <label>
            NRS
            <input value={calculator.nrs} onChange={(event) => setCalculator({ ...calculator, nrs: event.target.value })} inputMode="numeric" />
          </label>
        </div>
        <div className="protocol-toolbar compact-toolbar">
          <button type="button" className={actionFeedback?.key === 'calculator-run' ? 'action-confirmed' : ''} onClick={calculateMedication}>
            {actionFeedback?.key === 'calculator-run' ? 'Berechnet' : 'SOP berechnen'}
          </button>
        </div>
        {calculatorResult && (
          <div className="support-grid">
            <article>
              <h3>Berechnete Medikation</h3>
              {(calculatorResult.medications || []).length === 0 && <p className="muted">Keine konkrete Medikation in diesem Entscheidungszweig.</p>}
              {(calculatorResult.medications || []).map((item, index) => {
                const wasAccepted = acceptedCalculatorMedication?.index === index && acceptedCalculatorMedication?.text === item;
                return (
                  <div className={`support-row support-row-action${wasAccepted ? ' support-row-confirmed' : ''}`} key={`calc-med-${index}`}>
                    <strong>{index + 1}</strong>
                    <span>{item}</span>
                    <button type="button" onClick={() => addCalculatedMedication(item, index)}>
                      {wasAccepted || actionFeedback?.key === `calculator-med-${index}` ? 'Übernommen' : 'Übernehmen'}
                    </button>
                    {wasAccepted && <em aria-live="polite">In Maßnahmen übernommen</em>}
                  </div>
                );
              })}
            </article>
            <article>
              <h3>Handlungshilfe</h3>
              {(calculatorResult.actions || []).map((item, index) => (
                <div className="support-row" key={`calc-action-${index}`}>
                  <strong>{index + 1}</strong>
                  <span>{item}</span>
                </div>
              ))}
              {(calculatorResult.notes || []).map((item, index) => (
                <div className="support-note" key={`calc-note-${index}`}>{item}</div>
              ))}
            </article>
          </div>
        )}
      </section>}

      {protocolSection === 'massnahmen' && <section className="work-panel">
        <div className="section-head">
          <h2>Maßnahmen & Medikation</h2>
          <span>chronologisch dokumentieren</span>
        </div>

        <div className="list-head">
          <h3>Maßnahmen</h3>
          <button type="button" onClick={addMeasure}>Maßnahme hinzufügen</button>
        </div>
        <div className="dynamic-list">
          {(massnahmen.timeline || []).map((item, index) => (
            <div className="dynamic-row" key={`measure-${index}`}>
              <input placeholder="Zeit" value={item.zeit || ''} onChange={(event) => updateMeasure(index, 'zeit', event.target.value)} />
              <input placeholder="Maßnahme" value={item.massnahme || ''} onChange={(event) => updateMeasure(index, 'massnahme', event.target.value)} />
              <button type="button" onClick={() => removeMeasure(index)}>Entfernen</button>
            </div>
          ))}
          {(massnahmen.timeline || []).length === 0 && <p className="muted">Noch keine Maßnahmen dokumentiert.</p>}
        </div>

        <div className="list-head">
          <h3>Medikation</h3>
          <button type="button" onClick={addMedication}>Medikation hinzufügen</button>
        </div>
        <div className="dynamic-list">
          {(massnahmen.medikation || []).map((item, index) => (
            <div className="dynamic-row medication-row" key={`medication-${index}`}>
              <input placeholder="Zeit" value={item.zeit || ''} onChange={(event) => updateMedication(index, 'zeit', event.target.value)} />
              <input placeholder="Medikament" value={item.medikament || ''} onChange={(event) => updateMedication(index, 'medikament', event.target.value)} />
              <input placeholder="Dosis" value={item.dosis || ''} onChange={(event) => updateMedication(index, 'dosis', event.target.value)} />
              <input placeholder="Weg" value={item.weg || ''} onChange={(event) => updateMedication(index, 'weg', event.target.value)} />
              <button type="button" onClick={() => removeMedication(index)}>Entfernen</button>
            </div>
          ))}
          {(massnahmen.medikation || []).length === 0 && <p className="muted">Noch keine Medikation dokumentiert.</p>}
        </div>
      </section>}

      {protocolSection === 'reanimation' && <section className="work-panel">
        <div className="section-head">
          <h2>Reanimation</h2>
          <span>CPR, Defibrillation, ROSC und Notarzt</span>
        </div>

        <div className="form-grid">
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={Boolean(reanimation.active)}
              onChange={(event) => updateReanimation('active', event.target.checked)}
            />
            Reanimation durchgeführt
          </label>
          <label>
            Initialrhythmus
            <select value={reanimation.initial_rhythm || ''} onChange={(event) => updateReanimation('initial_rhythm', event.target.value)}>
              <option value="">Keine Angabe</option>
              <option value="Kammerflimmern">Kammerflimmern</option>
              <option value="pulslose ventrikuläre Tachykardie">pulslose ventrikuläre Tachykardie</option>
              <option value="Asystolie">Asystolie</option>
              <option value="PEA">PEA</option>
              <option value="AED-Analyse ohne Schockempfehlung">AED-Analyse ohne Schockempfehlung</option>
              <option value="unbekannt">unbekannt</option>
            </select>
          </label>
          <label>
            CPR-Beginn
            <input value={reanimation.cpr_start || ''} onChange={(event) => updateReanimation('cpr_start', event.target.value)} placeholder="z.B. 20:14" />
          </label>
          <label>
            CPR-Ende / Übergabe
            <input value={reanimation.cpr_end || ''} onChange={(event) => updateReanimation('cpr_end', event.target.value)} placeholder="z.B. 20:42" />
          </label>
          <label>
            ROSC
            <select value={reanimation.rosc || ''} onChange={(event) => updateReanimation('rosc', event.target.value)}>
              <option value="">Keine Angabe</option>
              <option value="Ja">Ja</option>
              <option value="Nein">Nein</option>
              <option value="intermittierend">intermittierend</option>
            </select>
          </label>
          <label>
            ROSC-Zeit
            <input value={reanimation.rosc_time || ''} onChange={(event) => updateReanimation('rosc_time', event.target.value)} placeholder="z.B. 20:31" />
          </label>
          <label>
            No-flow-Zeit
            <input value={reanimation.no_flow || ''} onChange={(event) => updateReanimation('no_flow', event.target.value)} placeholder="z.B. unbekannt / ca. 2 min" />
          </label>
          <label>
            Low-flow-Zeit
            <input value={reanimation.low_flow || ''} onChange={(event) => updateReanimation('low_flow', event.target.value)} placeholder="z.B. ca. 18 min" />
          </label>
          <label className="checkbox-field">
            <input
              type="checkbox"
              checked={Boolean(reanimation.mechanical_cpr)}
              onChange={(event) => updateReanimation('mechanical_cpr', event.target.checked)}
            />
            Mechanische Reanimationshilfe eingesetzt
          </label>
          <label>
            Ausgang
            <select value={reanimation.outcome || ''} onChange={(event) => updateReanimation('outcome', event.target.value)}>
              <option value="">Keine Angabe</option>
              <option value="Transport nach ROSC">Transport nach ROSC</option>
              <option value="Transport unter CPR">Transport unter CPR</option>
              <option value="Übergabe an Notarzt">Übergabe an Notarzt</option>
              <option value="Reanimation beendet">Reanimation beendet</option>
            </select>
          </label>
        </div>

        <div className="list-head">
          <h3>Defibrillationen</h3>
          <button type="button" onClick={addShock}>Schock hinzufügen</button>
        </div>
        <div className="dynamic-list">
          {(reanimation.shocks || []).map((item, index) => (
            <div className="dynamic-row shock-row" key={`shock-${index}`}>
              <input placeholder="Zeit" value={item.zeit || ''} onChange={(event) => updateShock(index, 'zeit', event.target.value)} />
              <input placeholder="Energie/J" value={item.energie || ''} onChange={(event) => updateShock(index, 'energie', event.target.value)} inputMode="numeric" />
              <input placeholder="Rhythmus vor/nach Schock" value={item.rhythmus || ''} onChange={(event) => updateShock(index, 'rhythmus', event.target.value)} />
              <button type="button" onClick={() => removeShock(index)}>Entfernen</button>
            </div>
          ))}
          {(reanimation.shocks || []).length === 0 && <p className="muted">Noch keine Defibrillation dokumentiert.</p>}
        </div>

        <div className="form-grid reanimation-detail-grid">
          <label>
            Atemweg / Beatmung
            <textarea value={reanimation.airway || ''} onChange={(event) => updateReanimation('airway', event.target.value)} rows={4} placeholder="z.B. BMV, supraglottischer Atemweg, Tubus, Kapnographie" />
          </label>
          <label>
            Zugang
            <textarea value={reanimation.access || ''} onChange={(event) => updateReanimation('access', event.target.value)} rows={4} placeholder="z.B. i.v., i.o., Lage, Besonderheiten" />
          </label>
          <label>
            Medikamente während CPR
            <textarea value={reanimation.meds || ''} onChange={(event) => updateReanimation('meds', event.target.value)} rows={4} placeholder="z.B. Adrenalin 1 mg i.v. 20:18, Amiodaron ..." />
          </label>
          <label>
            Notizen / Verlauf
            <textarea value={reanimation.notes || ''} onChange={(event) => updateReanimation('notes', event.target.value)} rows={4} placeholder="z.B. Laienreanimation, AED vor Eintreffen, Rhythmuswechsel, Transportentscheidung" />
          </label>
          <label>
            Notarzt alarmiert
            <input value={reanimation.notarzt_alarm || ''} onChange={(event) => updateReanimation('notarzt_alarm', event.target.value)} placeholder="z.B. 20:12" />
          </label>
          <label>
            Notarzt eingetroffen
            <input value={reanimation.notarzt_arrival || ''} onChange={(event) => updateReanimation('notarzt_arrival', event.target.value)} placeholder="z.B. 20:24" />
          </label>
          <label>
            Notarzt übernimmt
            <input value={reanimation.notarzt_takeover || ''} onChange={(event) => updateReanimation('notarzt_takeover', event.target.value)} placeholder="z.B. 20:25 / ja / nein" />
          </label>
        </div>
      </section>}

      {protocolSection === 'abschluss' && <section className="work-panel">
        <div className="section-head">
          <h2>Übergabe</h2>
          <span>Ziel, Eigentum, Lagerung und SINNHAFT-Vorschlag</span>
        </div>
        <div className="handover-layout">
          <fieldset>
            <legend>Übergabedaten</legend>
            <label>
              Ziel / Empfänger
              <input value={uebergabe.ziel || ''} onChange={(event) => updateUebergabe('ziel', event.target.value)} />
            </label>
            <label>
              Übergabetext frei
              <textarea value={uebergabe.text || ''} onChange={(event) => updateUebergabe('text', event.target.value)} rows={5} />
            </label>
            <div className="form-grid handover-extra-grid">
              <div className="choice-field full-span">
                <span>Lagerung / Transfertechnik</span>
                <select value="" onChange={(event) => addUebergabeOption('lagerung', event.target.value)}>
                  <option value="">Auswahl hinzufügen</option>
                  {handoverQuickOptions.lagerung.map((option) => <option key={`lagerung-${option}`} value={option}>{option}</option>)}
                </select>
                <textarea value={uebergabe.lagerung || ''} onChange={(event) => updateUebergabe('lagerung', event.target.value)} rows={2} placeholder="Weitere Lagerung/Transfertechnik ergänzen" />
              </div>
              <label>
                Krankenkassenkarte
                <select value={uebergabe.krankenkassenkarte || ''} onChange={(event) => updateUebergabe('krankenkassenkarte', event.target.value)}>
                  <option value="">Keine Angabe</option>
                  <option value="mitgegeben">mitgegeben</option>
                  <option value="bei Patient/in verblieben">bei Patient/in verblieben</option>
                  <option value="an Klinik übergeben">an Klinik übergeben</option>
                  <option value="nicht vorhanden">nicht vorhanden</option>
                  <option value="bei Angehörigen">bei Angehörigen</option>
                </select>
              </label>
              <div className="choice-field full-span">
                <span>Wertsachen / Eigentum</span>
                <select value="" onChange={(event) => addUebergabeOption('wertsachen', event.target.value)}>
                  <option value="">Auswahl hinzufügen</option>
                  {handoverQuickOptions.wertsachen.map((option) => <option key={`wertsachen-${option}`} value={option}>{option}</option>)}
                </select>
                <textarea value={uebergabe.wertsachen || ''} onChange={(event) => updateUebergabe('wertsachen', event.target.value)} rows={2} placeholder="Weitere Wertsachen oder Übergabeort ergänzen" />
              </div>
              <div className="choice-field full-span">
                <span>Patientenunterlagen / Medikamente</span>
                <select value="" onChange={(event) => addUebergabeOption('unterlagen', event.target.value)}>
                  <option value="">Auswahl hinzufügen</option>
                  {handoverQuickOptions.unterlagen.map((option) => <option key={`unterlagen-${option}`} value={option}>{option}</option>)}
                </select>
                <textarea value={uebergabe.unterlagen || ''} onChange={(event) => updateUebergabe('unterlagen', event.target.value)} rows={2} placeholder="Weitere Unterlagen oder Medikamente ergänzen" />
              </div>
              <label>
                Begleitperson / Angehörige
                <input value={uebergabe.begleitperson || ''} onChange={(event) => updateUebergabe('begleitperson', event.target.value)} placeholder="z.B. Ehepartner fährt mit / informiert" />
              </label>
              <label>
                Besonderheiten bei Übergabe
                <input value={uebergabe.besonderheiten || ''} onChange={(event) => updateUebergabe('besonderheiten', event.target.value)} placeholder="z.B. Isolation, Sprache, Betreuung, Dokumente fehlen" />
              </label>
            </div>
          </fieldset>
          <aside className="handover-preview">
            <h3>SINNHAFT-Vorschlag</h3>
            {sinnhaftPreviewRows.map(([label, value]) => (
              <p key={label}>
                <strong>{label}</strong>
                <span>{hasValue(value) ? value : 'noch offen'}</span>
              </p>
            ))}
          </aside>
        </div>
      </section>}

      {protocolSection === 'verweigerung' && <section className="work-panel refusal-panel">
        <div className="section-head">
          <h2>Patientenverweigerung</h2>
          <span>Textbaustein zum Kopieren</span>
        </div>
        <div className="form-grid">
          <label>
            Patient/in
            <input value={refusal.patient_name} onChange={(event) => updateRefusal('patient_name', event.target.value)} placeholder="Name oder frei lassen" />
          </label>
          <label>
            Vorgestellt dem/der
            <input value={refusal.presented_to} onChange={(event) => updateRefusal('presented_to', event.target.value)} placeholder="z.B. Notarzt / Ärztin / Rettungsdienst" />
          </label>
          <label>
            Einsatznummer
            <input value={refusal.case_number || patient.einsatz?.einsatznummer || ''} onChange={(event) => updateRefusal('case_number', event.target.value)} placeholder="wird aus Einsatzdaten übernommen" />
          </label>
          <label>
            Datum
            <input value={refusal.date} onChange={(event) => updateRefusal('date', event.target.value)} />
          </label>
          <label>
            Uhrzeit
            <input value={refusal.time} onChange={(event) => updateRefusal('time', event.target.value)} />
          </label>
          <label>
            Zeuge/Zeugin
            <input value={refusal.witness} onChange={(event) => updateRefusal('witness', event.target.value)} placeholder="optional" />
          </label>
          <fieldset className="full-span refusal-checks">
            <legend>Ablehnung</legend>
            <label>
              <input type="checkbox" checked={Boolean(refusal.refuse_treatment)} onChange={(event) => updateRefusal('refuse_treatment', event.target.checked)} />
              Rettungsdienstliche Behandlung abgelehnt
            </label>
            <label>
              <input type="checkbox" checked={Boolean(refusal.refuse_transport)} onChange={(event) => updateRefusal('refuse_transport', event.target.checked)} />
              Empfohlenen Transport abgelehnt
            </label>
            <label>
              <input type="checkbox" checked={Boolean(refusal.capacity_confirmed)} onChange={(event) => updateRefusal('capacity_confirmed', event.target.checked)} />
              Wach, orientiert und einwilligungsfähig eingeschätzt
            </label>
            <label>
              <input type="checkbox" checked={Boolean(refusal.advised_against)} onChange={(event) => updateRefusal('advised_against', event.target.checked)} />
              Verweigerung gegen ausdrücklichen Rat
            </label>
            <label>
              <input type="checkbox" checked={Boolean(refusal.signature_refused)} onChange={(event) => updateRefusal('signature_refused', event.target.checked)} />
              Patient/in verweigert Unterschrift
            </label>
          </fieldset>
          <label className="full-span">
            Freitext zur Verweigerung
            <input value={refusal.scope} onChange={(event) => updateRefusal('scope', event.target.value)} placeholder={buildRefusalScope(refusal)} />
          </label>
          <label className="full-span">
            Angegebener Grund
            <textarea value={refusal.reason} onChange={(event) => updateRefusal('reason', event.target.value)} rows={3} placeholder="z.B. möchte zu Hause verbleiben / lehnt Transport ab" />
          </label>
          <label className="full-span">
            Aufklärung über Risiken
            <textarea value={refusal.risks} onChange={(event) => updateRefusal('risks', event.target.value)} rows={3} />
          </label>
        </div>
        <div className="protocol-toolbar compact-toolbar">
          <button type="button" className={actionFeedback?.key === 'refusal-download' ? 'action-confirmed' : ''} onClick={downloadRefusalText}>
            {actionFeedback?.key === 'refusal-download' ? 'TXT vorbereitet' : 'TXT herunterladen'}
          </button>
          <button type="button" className={actionFeedback?.key === 'refusal-print' ? 'action-confirmed' : ''} onClick={printRefusalText}>
            {actionFeedback?.key === 'refusal-print' ? 'Druck geöffnet' : 'Drucken'}
          </button>
        </div>
        <div className="refusal-signature-grid">
          <div>
            <span>Patient/in</span>
            <strong>Unterschrift</strong>
          </div>
          <div>
            <span>Rettungsdienst</span>
            <strong>Unterschrift</strong>
          </div>
          <div>
            <span>Zeuge/Zeugin</span>
            <strong>{hasValue(refusal.witness) ? refusal.witness : 'Name / Unterschrift'}</strong>
          </div>
        </div>
        <textarea
          className="protocol-preview refusal-preview"
          value={refusalText}
          readOnly
          rows={16}
        />
      </section>}

      {protocolSection === 'protokoll' && <section className="work-panel">
        <div className="section-head">
          <h2>Dokumentation</h2>
          <span>Vorschau, Qualitätssicherung und Export</span>
        </div>
        <section className="protocol-toolbar protocol-actionbar protocol-actionbar-panel">
          <div className="toolbar-group toolbar-group-back">
            <button type="button" className="toolbar-button ghost" onClick={() => setProtocolSection('abschluss')}>
              <ArrowLeft size={16} /> Zurück
            </button>
          </div>
          <div className="toolbar-group toolbar-group-main">
            <button type="button" className={`toolbar-button${actionFeedback?.key === 'quality-check' ? ' action-confirmed' : ''}`} onClick={checkQuality}>
              <CheckCircle2 size={16} /> {actionFeedback?.key === 'quality-check' ? 'QS geprüft' : 'QS prüfen'}
            </button>
            <button type="button" className={`toolbar-button primary${actionFeedback?.key === 'generate-protocol' ? ' action-confirmed' : ''}`} onClick={generateProtocol}>
              <FileText size={16} /> {actionFeedback?.key === 'generate-protocol' ? 'Generiert' : 'Protokoll generieren'}
            </button>
            <button type="button" className={`toolbar-button icon-label${actionFeedback?.key === 'export-pdf' ? ' action-confirmed' : ''}`} onClick={exportDraftPdf}>
              <Download size={16} /> {actionFeedback?.key === 'export-pdf' ? 'PDF erstellt' : 'PDF'}
            </button>
            <button type="button" className={`toolbar-button icon-label${actionFeedback?.key === 'print-pdf' ? ' action-confirmed' : ''}`} onClick={printDraftPdf}>
              <Printer size={16} /> {actionFeedback?.key === 'print-pdf' ? 'Druck geöffnet' : 'Drucken'}
            </button>
          </div>
          <div className="toolbar-group toolbar-group-end">
            <button type="button" className={`toolbar-button save${actionFeedback?.key === 'save-draft' ? ' action-confirmed' : ''}`} onClick={saveDraft}>
              <Save size={16} /> {actionFeedback?.key === 'save-draft' ? 'Gespeichert' : 'Entwurf speichern'}
            </button>
            <button type="button" className={`toolbar-button danger${actionFeedback?.key === 'finish-case' ? ' action-confirmed' : ''}`} onClick={finishCase}>
              {actionFeedback?.key === 'finish-case' ? 'Archiviert' : forceFinish ? 'Mit Warnungen beenden' : 'Einsatz beenden'}
            </button>
          </div>
        </section>
        {qualityResult && (
          <div className={`quality-box quality-${qualityResult.level}`}>
            <div className="quality-overview">
              <div className="quality-score">
                <strong>{qualityResult.score}</strong>
                <span>QS-Punkte</span>
              </div>
              <div className="quality-summary">
                <div>
                  <strong>{qualityResult.ok_count}</strong>
                  <span>erfüllt</span>
                </div>
                <div>
                  <strong>{qualityResult.warning_count}</strong>
                  <span>Warnungen</span>
                </div>
                <div>
                  <strong>{qualityResult.critical_count}</strong>
                  <span>kritisch</span>
                </div>
              </div>
            </div>
            <div className="quality-list">
              {(qualityResult.items || []).filter((item) => item.status !== 'ok').map((item) => (
                <div className={`quality-item quality-item-${item.status}`} key={item.id}>
                  <AlertTriangle size={16} />
                  <div>
                    <strong>{item.label}</strong>
                    <span>{item.message}</span>
                  </div>
                </div>
              ))}
              {(qualityResult.items || []).filter((item) => item.status !== 'ok').length === 0 && (
                <div className="quality-item quality-item-ok">
                  <CheckCircle2 size={16} />
                  <div>
                    <strong>Keine Warnungen</strong>
                    <span>Die aktiven QS-Regeln sind erfüllt.</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        <textarea
          className="protocol-preview"
          value={generatedProtocol}
          onChange={(event) => setGeneratedProtocol(event.target.value)}
          placeholder="Noch keine Vorschau erzeugt."
          rows={18}
        />
      </section>}
    </main>
  );
}

function App() {
  const [session, setSession] = useState(() => {
    const legacy = localStorage.getItem('nana_session');
    if (legacy) {
      localStorage.removeItem('nana_session');
    }
    const raw = sessionStorage.getItem('nana_session');
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.employee ? { employee: parsed.employee, lastActivity: parsed.lastActivity || Date.now() } : null;
  });
  const [lockedSession, setLockedSession] = useState(() => {
    const raw = localStorage.getItem('nana_locked_session');
    return raw ? JSON.parse(raw) : null;
  });
  const [pendingSession, setPendingSession] = useState(null);
  const [online, setOnline] = useState(() => navigator.onLine);
  const [backendOnline, setBackendOnline] = useState(true);
  const [lastSync, setLastSync] = useState('');
  const [installPrompt, setInstallPrompt] = useState(null);
  const [standalone, setStandalone] = useState(() => isStandaloneApp());

  function handleLogin(result) {
    const nextSession = { employee: result.employee, lastActivity: Date.now() };
    sessionStorage.setItem('nana_session', JSON.stringify(nextSession));
    localStorage.removeItem('nana_locked_session');
    setLockedSession(null);
    setPendingSession(nextSession);
  }

  function handleRestoreSession(result) {
    const nextSession = { employee: result.employee, lastActivity: Date.now() };
    sessionStorage.setItem('nana_session', JSON.stringify(nextSession));
    localStorage.removeItem('nana_locked_session');
    setLockedSession(null);
    setSession(nextSession);
  }

  function lockCurrentSession(currentSession = session) {
    if (!currentSession?.employee) {
      handleLogout();
      return;
    }
    const nextLocked = {
      employee: currentSession.employee,
      lockedAt: Date.now(),
      lastActivity: currentSession.lastActivity || Date.now()
    };
    localStorage.setItem('nana_locked_session', JSON.stringify(nextLocked));
    sessionStorage.removeItem('nana_session');
    localStorage.removeItem('nana_session');
    setLockedSession(nextLocked);
    setPendingSession(null);
    setSession(null);
  }

  function handleLogout() {
    sessionStorage.removeItem('nana_session');
    localStorage.removeItem('nana_session');
    localStorage.removeItem('nana_locked_session');
    setLockedSession(null);
    setPendingSession(null);
    setSession(null);
  }

  function completeLoginTransition() {
    if (!pendingSession) return;
    setSession(pendingSession);
    setPendingSession(null);
  }

  useEffect(() => {
    if (!session) return undefined;

    function markActivity() {
      const raw = sessionStorage.getItem('nana_session');
      const current = raw ? JSON.parse(raw) : session;
      const nextSession = { ...current, lastActivity: Date.now() };
      sessionStorage.setItem('nana_session', JSON.stringify(nextSession));
    }

    function checkTimeout() {
      const raw = sessionStorage.getItem('nana_session');
      const current = raw ? JSON.parse(raw) : null;
      if (!current?.lastActivity || Date.now() - current.lastActivity > SESSION_TIMEOUT_MS) {
        lockCurrentSession(current || session);
      }
    }

    const events = ['click', 'keydown', 'pointermove', 'touchstart'];
    events.forEach((eventName) => window.addEventListener(eventName, markActivity));
    const interval = window.setInterval(checkTimeout, 30000);
    return () => {
      events.forEach((eventName) => window.removeEventListener(eventName, markActivity));
      window.clearInterval(interval);
    };
  }, [session]);

  useEffect(() => {
    function handleSessionExpired() {
      if (session?.employee) {
        lockCurrentSession(session);
      }
    }
    window.addEventListener('nana-session-expired', handleSessionExpired);
    return () => window.removeEventListener('nana-session-expired', handleSessionExpired);
  }, [session]);

  useEffect(() => {
    function updateOnline() {
      setOnline(navigator.onLine);
    }

    async function checkBackend() {
      try {
        await api('/api/health');
        setBackendOnline(true);
      } catch {
        setBackendOnline(false);
      }
    }

    window.addEventListener('online', updateOnline);
    window.addEventListener('offline', updateOnline);
    checkBackend();
    const interval = window.setInterval(checkBackend, 30000);
    return () => {
      window.removeEventListener('online', updateOnline);
      window.removeEventListener('offline', updateOnline);
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    function handleBeforeInstallPrompt(event) {
      event.preventDefault();
      setInstallPrompt(event);
    }

    function handleInstalled() {
      setInstallPrompt(null);
      setStandalone(true);
    }

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleInstalled);
    };
  }, []);

  async function handleInstallApp() {
    if (!installPrompt) return;
    installPrompt.prompt();
    await installPrompt.userChoice.catch(() => null);
    setInstallPrompt(null);
    setStandalone(isStandaloneApp());
  }

  const connectivity = { online, backendOnline, lastSync };

  if (pendingSession) {
    return <LoginTransition session={pendingSession} onComplete={completeLoginTransition} />;
  }

  if (lockedSession) {
    return <ReauthLock lockedSession={lockedSession} onRestore={handleRestoreSession} onSwitchUser={handleLogout} />;
  }

  return session
    ? (
      <Dashboard
        session={session}
        onLogout={handleLogout}
        onSessionReplace={handleRestoreSession}
        connectivity={connectivity}
        onSync={setLastSync}
        installPromptAvailable={Boolean(installPrompt) && !standalone}
        onInstallApp={handleInstallApp}
      />
    )
    : <Login onLogin={handleLogin} />;
}

function isStandaloneApp() {
  return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
}

function getInitialDashboardView() {
  const view = new URLSearchParams(window.location.search).get('view');
  return ['protocol', 'refusal', 'cancelled', 'approach', 'hospital', 'icd10', 'devices'].includes(view) ? view : 'home';
}

function isLocalDevHost() {
  return ['localhost', '127.0.0.1'].includes(window.location.hostname) && window.location.port === '5173';
}

async function clearLocalServiceWorker() {
  if (!('serviceWorker' in navigator)) return;

  const registrations = await navigator.serviceWorker.getRegistrations();
  const hadController = Boolean(navigator.serviceWorker.controller);
  const cacheNames = 'caches' in window ? await caches.keys().catch(() => []) : [];

  await Promise.all(registrations.map((registration) => registration.unregister()));
  if ('caches' in window) {
    await Promise.all(cacheNames.map((cacheName) => caches.delete(cacheName)));
  }

  const resetNeeded = hadController || registrations.length > 0 || cacheNames.length > 0;
  if (resetNeeded && sessionStorage.getItem('nana_local_sw_reset') !== 'done') {
    sessionStorage.setItem('nana_local_sw_reset', 'done');
    window.location.reload();
  }
}

function registerProductionServiceWorker() {
  navigator.serviceWorker.register('/sw.js')
    .then((registration) => {
      registration.update().catch(() => {});
      registration.addEventListener('updatefound', () => {
        const worker = registration.installing;
        if (!worker) return;

        worker.addEventListener('statechange', () => {
          if (worker.state === 'installed' && navigator.serviceWorker.controller) {
            worker.postMessage({ type: 'SKIP_WAITING' });
          }
        });
      });
    })
    .catch(() => {});

  let refreshing = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (refreshing) return;
    refreshing = true;
    window.location.reload();
  });
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    if (isLocalDevHost()) {
      clearLocalServiceWorker().catch(() => {});
      return;
    }

    registerProductionServiceWorker();
  });
}

createRoot(document.getElementById('root')).render(<App />);
