"""Kurzanleitungen fuer den Geraete-Guide.

Die Inhalte sind bewusst als aufgabenbezogene Kurzreferenz formuliert. Sie
ersetzen weder Einweisung noch die zum konkreten Geraet gehoerende aktuelle
Gebrauchsanweisung.
"""

DEVICE_GUIDES = {
    "Perfusor Space (B. Braun)": {
        "icon": "💉",
        "model_note": "Perfusor® Space – Spritzenpumpe",
        "source_label": "B. Braun Kurz-Gebrauchsanweisung",
        "source_url": "https://www.bbraun.de/content/dam/catalog/bbraun/bbraunProductCatalog/S/AEM2015/de-de/b5/flyer-kurz-gba-perfusorspace.pdf",
        "topics": {
            "Spritze einlegen und starten": [
                "Gerät einschalten und die Pumpenklappe öffnen.",
                "Spritze korrekt einlegen; der Spritzenbügel liegt rechts am Gehäuse.",
                "Pumpenklappe und Spritzenbügel schließen.",
                "Den vom Gerät erkannten Spritzentyp kontrollieren und bestätigen.",
                "Start-up-Menü durchgehen, Förderrate eingeben und alle Therapieparameter nochmals prüfen.",
                "Patientenverbindung kontrollieren und die Infusion über die Starttaste beginnen.",
            ],
            "Förderrate ändern": [
                "Pumpe stoppen oder – wenn lokal freigegeben – die Ratenänderung während der laufenden Infusion aufrufen.",
                "Förderrate im Hauptmenü anwählen und den neuen Wert eingeben.",
                "Neuen Wert am Display bewusst gegenprüfen.",
                "Änderung bestätigen und Infusion wieder starten beziehungsweise fortsetzen.",
            ],
            "Spritzenwechsel": [
                "Infusion stoppen und die Verbindung zum Patienten unterbrechen.",
                "Spritzenbügel öffnen und Anzeigen beziehungsweise Rückfragen des Geräts beachten.",
                "Neue Spritze einlegen, Bügel und Klappe schließen und den erkannten Spritzentyp prüfen.",
                "Leitung bei Bedarf nach lokaler Vorgabe entlüften – niemals mit bestehender Patientenverbindung.",
                "Therapieparameter kontrollieren, Patientenverbindung herstellen und Infusion fortsetzen.",
            ],
            "Schichtbeginn-Kurzcheck": [
                "Gehäuse, Netzteil, Halterung, Leitung und Spritzenbügel auf sichtbare Schäden prüfen.",
                "Gerät einschalten und Selbsttest sowie Displaymeldungen vollständig abwarten.",
                "Akku-/Netzstatus, Tastatur, Display und akustische Signale prüfen.",
                "Benötigte Spritzengrößen und Verbrauchsmaterial nach lokaler Checkliste vervollständigen.",
                "Nur bei bestandenem Check einsatzbereit melden; Abweichungen nach Betreiberprozess kennzeichnen.",
            ],
        },
    },
    "corpuls3": {
        "icon": "❤️",
        "model_note": "corpuls3 / corpuls3 SLIM – modularer Monitor und Defibrillator",
        "source_label": "corpuls Produkt- und Supportbereich",
        "source_url": "https://corpuls.world/produkte/corpuls3/",
        "topics": {
            "System aufbauen und starten": [
                "Monitor, Patientenbox und Defibrillator/Pacer auf Vollständigkeit und sichtbare Schäden prüfen.",
                "Module verbinden beziehungsweise den vorgesehenen gekoppelten Betrieb kontrollieren.",
                "Gerät einschalten und Startmeldungen sowie Modul- und Akkustatus abwarten.",
                "Vorkonnektierte Sensoren aus den Taschen entnehmen und passend zur Messung anschließen.",
                "Kurven, Messwerte, Alarmgrenzen und verbleibende Betriebszeit im Display prüfen.",
            ],
            "Monitoring beginnen": [
                "Patientenbox beim Patienten positionieren und benötigte Sensoren auswählen.",
                "EKG, SpO₂, NIBD und gegebenenfalls weitere Sensoren korrekt anschließen.",
                "Signalqualität jeder Kurve prüfen; Artefakte nicht als Messwert übernehmen.",
                "Messung starten und patientenbezogene Alarmgrenzen nach lokaler Vorgabe kontrollieren.",
                "Bei Modultrennung Verbindung, Akkurestzeit und fortlaufende Datenübertragung beobachten.",
            ],
            "Schichtbeginn-Kurzcheck": [
                "Alle drei Module, Taschen, Kabel, Sensoren und Therapieelektroden auf Vollständigkeit prüfen.",
                "Akkus und Ladezustände jedes Moduls kontrollieren.",
                "Gerät starten und Status-, Alarm- und Verbindungsmeldungen prüfen.",
                "Druckerpapier, Elektroden und benötigtes Zubehör nach lokaler Checkliste ergänzen.",
                "Für Defibrillator-/Pacer-Prüfungen ausschließlich die freigegebene Betreiberanweisung verwenden.",
            ],
        },
    },
    "corpuls1": {
        "icon": "🫀",
        "model_note": "corpuls1 – kompakter Monitor und Defibrillator",
        "source_label": "corpuls Produkt- und Supportbereich",
        "source_url": "https://corpuls.world/produkte/corpuls1/",
        "topics": {
            "Gerät starten und überwachen": [
                "Gerät und Zubehör auf sichtbare Schäden und Vollständigkeit prüfen.",
                "corpuls1 einschalten und Startmeldungen sowie Akkurestzeit kontrollieren.",
                "Benötigte vorkonnektierte Kabel und Sensoren aus den Taschen entnehmen.",
                "EKG beziehungsweise Pulsoxymetrie anschließen und die Signalqualität prüfen.",
                "Angezeigte Parameter und Alarmgrenzen kontrollieren.",
            ],
            "AED-Bereitschaft herstellen": [
                "Gerät einschalten und den vorgesehenen AED-Modus gemäß lokaler Freigabe aufrufen.",
                "Vorkonnektierte Therapieelektroden auf Verpackung, Verfallsdatum und Anschluss prüfen.",
                "Elektroden nach Darstellung auf der Verpackung anbringen.",
                "Sprach- und Displayanweisungen befolgen; während Analyse und Schockabgabe Patientenkontakt ausschließen.",
                "Reanimationsmaßnahmen und Zeiten parallel dokumentieren.",
            ],
            "Schichtbeginn-Kurzcheck": [
                "Gehäuse, Taschen, Kabel und Sensoren kontrollieren.",
                "Akkustatus und Fahrzeug-/Netzversorgung prüfen.",
                "Therapieelektroden, Druckerpapier und Verbrauchsmaterial kontrollieren.",
                "Start- und Gerätestatus prüfen; Fehlermeldungen nicht quittieren, ohne ihre Ursache zu klären.",
                "Gerätespezifischen Defibrillatorcheck nach lokaler Betreiberanweisung durchführen.",
            ],
        },
    },
    "ACCUVAC": {
        "icon": "🌬️",
        "model_note": "WEINMANN ACCUVAC – Modell am Typenschild prüfen (Lite/Pro/Rescue)",
        "source_label": "WEINMANN Emergency Download-Center",
        "source_url": "https://www.weinmann-emergency.com/de/download/downloadcenter/",
        "topics": {
            "Absaugbereitschaft herstellen": [
                "Exaktes ACCUVAC-Modell am Typenschild prüfen; Zubehör und Bedienung unterscheiden sich je nach Variante.",
                "Sekretbehälter, Deckel, Filter und Schlauchsystem korrekt zusammensetzen und auf Dichtheit prüfen.",
                "Patientenschlauch anschließen und einen geeigneten Absaugkatheter bereitlegen.",
                "Gerät einschalten und die benötigte Saugleistung nach lokaler Vorgabe einstellen.",
                "Funktion kurz durch Verschließen des Patientenschlauchs prüfen; Anzeigen und Geräusch beachten.",
                "Erst danach am Patienten verwenden und Behälterfüllstand laufend beobachten.",
            ],
            "Behälter wechseln": [
                "Absaugung beenden, Gerät ausschalten und persönliche Schutzausrüstung beachten.",
                "Patientenschlauch sichern und kontaminationsarm vom Behältersystem trennen.",
                "Behälter beziehungsweise Einwegbeutel entsprechend dem vorhandenen Modell entnehmen und verschließen.",
                "Neues System korrekt einsetzen; Deckel, Filter und alle Schlauchanschlüsse kontrollieren.",
                "Dichtheits-/Funktionsprüfung durchführen und Material fachgerecht entsorgen.",
            ],
            "Schichtbeginn-Kurzcheck": [
                "Modell, Behältersystem und passenden Anleitungssatz eindeutig zuordnen.",
                "Gehäuse, Schläuche, Filter, Behälter, Ladehalterung und Zubehör prüfen.",
                "Akku-/Ladestatus kontrollieren und Gerät einschalten.",
                "Kurzen Dichtheits- und Sogtest gemäß modellspezifischer Gebrauchsanweisung durchführen.",
                "Ersatzbehälter, Katheter und persönliche Schutzausrüstung vervollständigen.",
            ],
        },
    },
    "Laerdal LSU": {
        "icon": "🫁",
        "model_note": "Laerdal Suction Unit – Serres- oder Mehrwegbehälter beachten",
        "source_label": "Laerdal LSU Gebrauchsanweisung und Support",
        "source_url": "https://laerdal.com/gb/ProductDownloads.aspx?productId=234",
        "topics": {
            "Gerätetest": [
                "Schlauchsystem, Behälter und Filter vollständig und korrekt montieren.",
                "LSU einschalten und den integrierten TEST-Modus starten.",
                "Den Anweisungen am Gerät folgen und den Schlauch nur dann verschließen, wenn das Testprogramm dazu auffordert.",
                "Test auf Blockade, Vakuumaufbau, maximal erreichbares Vakuum und Leckage vollständig abwarten.",
                "Nur bei bestandenem Test als einsatzbereit kennzeichnen; Fehler nach Betreiberprozess bearbeiten.",
            ],
            "Absaugung vorbereiten": [
                "Serres- oder Mehrwegbehältersystem identifizieren und Anschlüsse kontrollieren.",
                "Patientenschlauch und geeigneten Absaugkatheter anschließen.",
                "Gerät einschalten und Vakuum am großen Regler gemäß Patient und lokaler Vorgabe wählen.",
                "Tatsächlich aufgebautes Vakuum an der Anzeige kontrollieren.",
                "Während der Anwendung Behälterfüllstand, Akku und Störungsanzeige beobachten.",
            ],
            "Schichtbeginn-Kurzcheck": [
                "Gerät, Behälter, Schläuche, Filter und Ladehalterung auf Schäden und Vollständigkeit prüfen.",
                "Akku- und externe Stromanzeige kontrollieren.",
                "Integrierten Gerätetest vollständig durchführen.",
                "Ersatzbeutel beziehungsweise Mehrwegzubehör und Absaugkatheter vervollständigen.",
                "Reinigungs- und Wechselintervalle nach Betreiberanweisung prüfen.",
            ],
        },
    },
    "MEDUMAT Standard²": {
        "icon": "🫧",
        "model_note": "WEINMANN MEDUMAT Standard² – Softwarestand am Gerät beachten",
        "source_label": "WEINMANN Download-Center und Gerätesimulation",
        "source_url": "https://www.weinmann-emergency.com/de/download/downloadcenter/",
        "topic_actions": {
            "Simulation öffnen": {
                "label": "🖥️ MEDUMAT-Simulator herunterladen ↗",
                "url": "https://weinmann-emergency.canto.de/direct/other/a2oofh0s7l48p6eh1p3jenm53g/2t90BKBvMeu-glvC9B0Frdohrsk/original?content-type=application%2Fzip&name=MEDUMAT-Standard2-PC-Simulation_FW-5-13.zip",
                "hint": "Offizielle WEINMANN-PC-Simulation, Version 5.13. Der Klick startet den Download direkt beim Hersteller.",
            }
        },
        "topics": {
            "Beatmungsbereitschaft herstellen": [
                "Gerät, Schlauchsystem, Patientenventil, Maske und Sauerstoffversorgung prüfen.",
                "Sauerstoffversorgung sicher anschließen und ausreichenden Vorrat kontrollieren.",
                "Schlauchsystem entsprechend der vorhandenen Konfiguration vollständig verbinden.",
                "Gerät einschalten, Selbsttest und alle Meldungen abwarten.",
                "Patientengruppe und vorgesehenen Modus nach lokaler SOP auswählen.",
                "Parameter vollständig gegenprüfen, bevor die Verbindung zum Patienten hergestellt wird.",
            ],
            "Während der Beatmung": [
                "Patient, Thoraxbewegung, Beatmungsdruck und angezeigte Kurven/Werte kontinuierlich beurteilen.",
                "Alarme sofort anhand von Patient, Schlauchsystem und Gerätemeldung prüfen.",
                "Sitz der Maske beziehungsweise des Atemwegs und Dichtheit des Systems kontrollieren.",
                "Sauerstoffvorrat, Akku und verbleibende Betriebszeit beobachten.",
                "Parameteränderungen nur gemäß Qualifikation und lokaler SOP vornehmen und dokumentieren.",
            ],
            "Schichtbeginn-Kurzcheck": [
                "Gehäuse, Halterung, Stromversorgung, O₂-Anschluss und Zubehör kontrollieren.",
                "Schlauchsystem, Patientenventil, Filter und Masken vollständig bereitlegen.",
                "Gerät einschalten und vorgesehenen Funktions-/Selbsttest durchführen.",
                "Akku, Sauerstoffvorrat, Alarmfunktion und Softwarestand prüfen.",
                "Bekannte Hersteller-Sicherheitshinweise und lokale Betreiberinformationen berücksichtigen.",
            ],
            "Simulation öffnen": [
                "Die offizielle WEINMANN-Simulationssoftware am Schulungsrechner öffnen.",
                "Passende MEDUMAT-Standard²-Version auswählen.",
                "Bedienabläufe ohne Patientenkontakt trainieren; Simulation nicht als Ersatz für Einweisung verwenden.",
                "Abweichungen zwischen Simulator, Softwarestand und realem Gerät beachten.",
            ],
        },
    },
}
