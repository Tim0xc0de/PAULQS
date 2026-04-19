# Projektdurchführung – PAULQS Cube Inspection System

> Dokumentation der einzelnen Arbeitsschritte und Erläuterung zentraler Entscheidungspunkte.  
> Vorgehensmodell: **Spiralmodell** – jede Iteration liefert ein lauffähiges Inkrement, das in der nächsten Iteration erweitert wird.

---

## Iterationsübersicht

| # | Schwerpunkt | Wesentliche Arbeitspakete |
|---|-------------|--------------------------|
| 1 | Planung & Infrastruktur | Ist-Analyse, Systemkonzept, Technologie-Stack, Datenbankmodelle |
| 2 | Robotersteuerung | Greif- und Ablege-Funktionen, Inspektions- und Sortiersequenz |
| 3 | Bildverarbeitung | Kameraanbindung, Farberkennung, Augenzahl-Erkennung |
| 4 | API – Endpunkte & Datenmodell | REST-Endpunkte, Schemas, Repository-Pattern, Datenzugriffsschicht |
| 5 | API – Inspektionsablauf | Inspektions-Service, SOLL-/IST-Vergleich, Bildablage |
| 6 | API – Sortierung, Logging & Status | Sortier-Service, Logging, Healthcheck, Kalibrierung per API |
| 7 | Kameragehäusekonzept & Modell | Anforderungen definieren, Konzeptskizze, 3D-Modell in Fusion 360 |
| 8 | Kameragehäuse Drucken & Montage | Slicing, Druckparameter, Druck, Nachbearbeitung, Montage & Ausrichtung |
| 9 | Integration & End-to-End | Modulzusammenführung, Deployment, Fehlerbehandlung |
| 10 | Dokumentation & Abschluss | Projektdokumentation, Deployment-Anleitung, Präsentation |

---

## Iteration 1 – Planung & Infrastruktur

### Arbeitsschritte

1. **Ist-Analyse:** Vorhandene Hardware gesichtet (Niryo-Roboterarm mit integrierter Kamera, Greifer, Netzwerkanbindung). Randbedingungen erfasst: kein externer Server verfügbar, System muss autark auf dem Roboter laufen.
2. **Systemkonzept:** Modulare Schichtenarchitektur entworfen – drei Schichten: API-Schicht, Anwendungsschicht, Infrastrukturschicht (Roboter, Vision, Datenbank). Jede Schicht ist unabhängig austauschbar.
3. **Technologie-Stack festgelegt:**
   - **FastAPI** als Web-Framework (asynchrone Background-Tasks für die Inspektion).
   - **SQLite + SQLAlchemy** als Datenbank (kein separater DB-Server nötig, ideal für Embedded-Betrieb).
   - **OpenCV** für die Bildverarbeitung.
   - **pyniryo** als offizielles SDK für den Niryo-Roboter.
   - **Pydantic v2** für Eingabe-/Ausgabevalidierung.
4. **Datenbankmodelle definiert:** Drei Tabellen – `configurations` (Soll-Vorgaben), `inspections` (Prüfergebnisse), `system_logs` (Betriebsprotokoll). Modelle in `models.py` als SQLAlchemy-Klassen umgesetzt.
5. **Projektstruktur angelegt:** Verzeichnisstruktur nach fachlichen Modulen (`api/`, `application/`, `infrastructure/robot/`, `infrastructure/vision/`, `infrastructure/database/`, `utils/`).

### Entscheidungspunkte

- **Warum FastAPI statt Flask?**  
  FastAPI bietet native Unterstützung für `BackgroundTasks`. Die Inspektion dauert mehrere Sekunden (Roboterbewegung, Bildaufnahme, Analyse). Mit `BackgroundTasks` kann der API-Aufruf sofort eine Antwort liefern, während die Inspektion im Hintergrund läuft. Flask hätte hierfür eine zusätzliche Task-Queue (z. B. Celery) benötigt – ein zu hoher Overhead für ein Embedded-System.

- **Warum SQLite statt PostgreSQL?**  
  Das System läuft direkt auf dem Niryo-Roboter. SQLite benötigt keinen separaten Datenbankprozess, ist dateibasiert und erfordert keinerlei Konfiguration. Für den erwarteten Datendurchsatz (wenige Inspektionen pro Minute) ist SQLite ausreichend.

- **Warum drei separate Tabellen statt einer?**  
  `configurations` und `inspections` sind über einen Fremdschlüssel (1:n) verbunden. Eine Konfiguration kann mehrfach geprüft werden, ohne die Soll-Daten zu duplizieren. `system_logs` ist bewusst entkoppelt (kein FK), damit Logs auch ohne Inspektionskontext geschrieben werden können (z. B. Systemstart, Verbindungsfehler).

---

## Iteration 2 – Robotersteuerung

### Arbeitsschritte

1. **`robot_controller.py` implementiert:** Klasse `RobotController` mit Methoden für Verbindung (`connect`), Vorbereitung (`prepare`), Bewegung (`move_to`), Greifen (`grip`), Loslassen (`release`) und Heimfahrt (`go_home`).
2. **`movements.py` als Config-Zugriffsschicht:** Liest alle Positionen, Sequenzen und Aktionen aus `robot_config.json`. Jede Funktion gibt genau einen Wert zurück – kein direkter Dateizugriff im Controller.
3. **`robot_config.json` strukturiert:** Alle Roboterpositionen als benannte 6-Gelenkwinkel-Arrays. Sequenz als geordnete Liste von Positionsnamen. Greifer- und Kamera-Aktionen als Referenzen auf Steps.
4. **Inspektionssequenz implementiert:** `run_sequence_with_capture()` fährt die Sequenz ab, öffnet/schließt den Greifer an konfigurierten Steps und nimmt Bilder an konfigurierten Positionen auf.
5. **Sortiersequenz implementiert:** `run_sort_sequence()` fährt nach der Inspektion entweder zur OK- oder NOK-Box (jeweils: über Box → Drop-Position → Greifer auf → Exit → Home).

### Entscheidungspunkte

- **Warum JSON-Config statt Hardcoding?**  
  Roboterpositionen müssen im Betrieb häufig nachjustiert werden (Teach-Mode). Mit einer externen JSON-Datei kann dies ohne Code-Änderung geschehen – auch über das Dashboard per PUT-Request. Kein Neustart nötig, da `movements.py` die Config bei jedem Aufruf neu lädt.

- **Warum eine generische Sequenz-Engine statt fester Schritte?**  
  Die Methode `run_sequence_with_capture()` iteriert über eine konfigurierbare Sequenzliste. Greifer-Aktionen und Kamera-Auslösungen werden über `gripper_close_at`, `gripper_open_at` und `capture_at` gesteuert. Dadurch kann der Ablauf komplett in der JSON-Datei geändert werden – neue Positionen, andere Reihenfolge, mehr oder weniger Fotos – ohne eine einzige Zeile Python-Code anzufassen.

- **Warum eine Wartezeit vor dem Foto (`CAPTURE_WAIT = 3s`)?**  
  Nach einer Roboterbewegung schwingt der Arm minimal nach. Eine 3-Sekunden-Pause vor der Bildaufnahme stellt sicher, dass das Bild nicht verwackelt ist. Der Wert wurde empirisch ermittelt.

---

## Iteration 3 – Bildverarbeitung

### Arbeitsschritte

1. **`camera.py` implementiert:** Eine einzige Funktion `capture(robot)`, die über das pyniryo-SDK ein komprimiertes Bild abruft, als NumPy-Array dekodiert und als BGR-Bild zurückgibt.
2. **`image_processing.py` implementiert:** Zwei Kernfunktionen:
   - `get_orange_mask()` – HSV-Farbfilter für orange Würfel (H: 5–25, S: 150–255, V: 120–255). Morphologische Operationen (Close + Open mit 5×5-Kernel) bereinigen die Maske.
   - `get_dark_spots()` – Relativer Schwellwert basierend auf der Median-Helligkeit der Würfeloberfläche. Alles deutlich dunkler als der Median wird als Auge erkannt.
3. **`detection.py` implementiert:** Funktion `detect_cube()` mit Contour-Hierarchie-Ansatz (RETR_CCOMP):
   - Äußere Konturen = Würfelfläche (größte passende Kontur mit Fläche > 2000 px und annähernd quadratischem Seitenverhältnis).
   - Innere Konturen (Kinder der Würfelkontur) = Löcher = Augen.
   - Filterkriterien: Fläche 30–800 px, Zirkularität > 0.45.
   - Ausreißer-Entfernung über Median-Vergleich bei mehr als 2 Kandidaten.

### Entscheidungspunkte

- **Warum HSV-Farbraum statt RGB?**  
  HSV trennt Farbton (H), Sättigung (S) und Helligkeit (V). Dadurch können Beleuchtungsschwankungen über den V-Kanal toleriert werden, ohne die Farberkennung zu beeinträchtigen. Im RGB-Raum wäre eine robuste Orange-Erkennung bei wechselnden Lichtverhältnissen deutlich schwieriger.

- **Warum Contour-Hierarchie (RETR_CCOMP) statt einfacher Konturerkennung?**  
  `RETR_CCOMP` liefert eine zweistufige Hierarchie: äußere Konturen und deren direkte Kinder (Löcher). Augen sind physische Vertiefungen im Würfel und erscheinen als Löcher in der orangen Fläche. OpenCV erkennt diese Löcher direkt als Kind-Konturen – kein separater Grauwert-Threshold nötig. Dieser Ansatz ist robuster als der ursprüngliche Ansatz über `get_dark_spots()`, der bei Schattenwurf fehlerhafte Ergebnisse lieferte.

- **Warum Median-basierte Ausreißer-Entfernung?**  
  Bei Würfeln mit vielen Augen (5, 6) können Textur-Ritzen als kleine Konturen erscheinen. Der Median der Augen-Flächen ist ein stabiler Referenzwert. Konturen mit weniger als 40 % der Median-Fläche werden als Rauschen verworfen.

---

## Iteration 4 – API: Endpunkte & Datenmodell

### Arbeitsschritte

1. **`routes.py` implementiert:** REST-Endpunkte mit FastAPI-Router:
   - `POST /api/config` – Nimmt eine Soll-Konfiguration entgegen, speichert sie in der DB und startet die Inspektion als Background-Task.
   - `GET /api/inspections` – Gibt die letzten Prüfergebnisse zurück (paginiert über `limit`).
   - `GET /api/healthcheck` – Prüft Roboter-Verbindung, Kalibrierungsstatus und Kamera.
   - `POST /api/calibration` – Löst eine automatische Kalibrierung des Roboters aus.
   - `POST /api/learning-mode` – Aktiviert/deaktiviert den Freedrive-Modus.
   - `GET /api/current-joints` – Liest aktuelle Gelenkpositionen aus.
2. **`schemas.py` implementiert:** Pydantic-Modelle für Eingabe (`ConfigurationCreate`, `InspectionCreate`) und Ausgabe (`InspectionResponse`). Validator für `target_dots` / `actual_dots` konvertiert JSON-Strings transparent in Python-Listen.
3. **`dependencies.py` implementiert:** Generator-Funktion `get_db()` für FastAPI Dependency Injection – erzeugt eine DB-Session und schließt sie nach dem Request.
4. **`repository.py` implementiert:** Klasse `InspectionRepository` mit Methoden `save_config()`, `save_inspection()`, `get_all_inspections()`. Listen werden vor dem Speichern mit `json.dumps()` serialisiert.

### Entscheidungspunkte

- **Warum Repository-Pattern statt direkter DB-Zugriffe in den Routes?**  
  Das Repository kapselt alle Datenbankoperationen in einer eigenen Klasse. Die API-Schicht (`routes.py`) kennt keine SQLAlchemy-Queries. Vorteile: (1) Einheitliche Stelle für DB-Logik, (2) einfacheres Testing durch Austauschbarkeit des Repositories, (3) klare Trennung von API-Logik und Datenzugriff.

- **Warum `BackgroundTasks` statt synchroner Verarbeitung?**  
  Eine Inspektion dauert 30–60 Sekunden (Roboterbewegung + Bildaufnahme + Analyse). Ein synchroner API-Call würde den Client so lange blockieren. Mit `BackgroundTasks` antwortet der Server sofort mit der gespeicherten Konfiguration, und die Inspektion läuft im Hintergrund.

- **Warum `target_dots` als JSON-String in der DB?**  
  Die Augenzahlen sind eine Liste variabler Länge (z. B. `[1, 3, 5]`). SQLite unterstützt keine nativen Array-Typen. Ein JSON-String ist die pragmatische Lösung: kompakt, menschenlesbar und durch Pydantic-Validatoren transparent konvertierbar.

---

## Iteration 5 – API: Inspektionsablauf

### Arbeitsschritte

1. **`inspection_service.py` implementiert:** Zentrale Orchestrierungsfunktion `run_inspection(config_id)`, die den gesamten Ablauf in 6 Schritten steuert:
   - Schritt 1: Roboter verbinden.
   - Schritt 2: Roboter vorbereiten (Kalibrierung prüfen, Learning-Mode deaktivieren).
   - Schritt 3: Sequenz abfahren und Bilder aufnehmen.
   - Schritt 4: Jedes Bild analysieren (Würfelerkennung + Augenzählung).
   - Schritt 5: SOLL-/IST-Vergleich durchführen und Ergebnis in DB speichern.
   - Schritt 6: Würfel in die richtige Kiste sortieren.
2. **SOLL-/IST-Vergleich implementiert:** `sorted(actual_dots) == sorted(target_dots)` – die Reihenfolge der erkannten Augenzahlen spielt keine Rolle, da der Roboter die Seiten in beliebiger Reihenfolge fotografiert.
3. **Bildablage implementiert:** Roh- und Ergebnisbilder werden als `side_X_raw.jpg` und `side_X_result.jpg` im Verzeichnis `captures/` gespeichert. Ergebnisbilder enthalten eine Bounding-Box und die erkannte Augenzahl.
4. **Fehlerbehandlung:** Wenn der Roboter nicht erreichbar oder nicht kalibriert ist, wird ein leeres Ergebnis (`is_ok = False`) gespeichert und die Inspektion abgebrochen. Jeder Schritt ist in einen Try-Except-Block eingebettet.

### Entscheidungspunkte

- **Warum `sorted()` statt exakter Reihenfolge beim Vergleich?**  
  Der Roboter kann die Würfelseiten in beliebiger Reihenfolge fotografieren, abhängig von der Konfiguration der Kamerastationen. Ein positionsbasierter Vergleich wäre fehleranfällig. Durch `sorted()` wird nur geprüft, ob die erkannten Augenzahlen als Menge mit den Soll-Werten übereinstimmen.

- **Warum `is_ok` als vorab berechnetes Flag statt Echtzeit-Berechnung?**  
  Das Flag wird zum Zeitpunkt der Prüfung berechnet und in der Datenbank gespeichert. Dashboard-Abfragen (Fehlerquote, Historie) können direkt auf `is_ok` filtern, ohne den Vergleich jedes Mal neu durchzuführen. Das reduziert die Komplexität in der Datenzugriffsschicht.

- **Warum Rohbilder UND Ergebnisbilder speichern?**  
  Rohbilder ermöglichen nachträgliche Analyse, falls die Erkennung fehlerhaft war (z. B. um HSV-Werte anzupassen). Ergebnisbilder mit Bounding-Box und Augenzahl-Annotation dienen der schnellen visuellen Kontrolle im Dashboard.

---

## Iteration 6 – API: Sortierung, Logging & Status

### Arbeitsschritte

1. **`sorting_service.py` implementiert:** Funktion `sort_cube(controller, is_ok)`, die den Roboter nach der Inspektion zur passenden Kiste fährt:
   - `is_ok = True` → Sequenz: `sort_ok_above` → `sort_ok_drop` → Greifer auf → `sort_ok_exit` → Home.
   - `is_ok = False` → Sequenz: `sort_nok_above` → `sort_nok_drop` → Greifer auf → `sort_nok_exit` → Home.
2. **`logger.py` implementiert:** Zentrale Logging-Funktion `log(module, level, message)`. Schreibt parallel in die Konsole (`print`) und in die Datenbank-Tabelle `system_logs`. Erstellt automatisch eine eigene DB-Session – kann von überall ohne Session-Übergabe aufgerufen werden.
3. **Logging in alle Module integriert:** Jeder relevante Schritt in `robot_controller.py`, `inspection_service.py`, `sorting_service.py` und `routes.py` schreibt ein Log.
4. **Healthcheck-Endpunkt implementiert:** `GET /api/healthcheck` prüft drei Komponenten (Roboter-Verbindung, Kalibrierung, Kamera) und gibt den Gesamtstatus als JSON zurück.
5. **Kalibrierungs-Endpunkt implementiert:** `POST /api/calibration` löst `robot.calibrate_auto()` aus, ohne dass physischer Zugang zum Roboter nötig ist.

### Entscheidungspunkte

- **Warum ein eigener Logging-Mechanismus statt Pythons `logging`-Modul?**  
  Das Standard-`logging`-Modul schreibt in Dateien oder Konsole. Für das Dashboard werden die Logs jedoch in der Datenbank benötigt (Filter nach Modul, Level, Freitext). Eine dedizierte `log()`-Funktion schreibt in beide Kanäle (Konsole + DB) und ist überall ohne Konfiguration nutzbar.

- **Warum `system_logs` ohne Fremdschlüssel?**  
  Logs sollen auch dann geschrieben werden können, wenn kein Inspektionskontext existiert (z. B. Systemstart, Verbindungsabbruch). Ein Fremdschlüssel auf `inspections` würde diese Entkopplung verhindern. Außerdem können Logs unabhängig rotiert oder gelöscht werden, ohne die Inspektionsdaten zu beeinflussen.

- **Warum separate Sortier-Sequenzen (`sort_ok_sequence`, `sort_nok_sequence`) in der Config?**  
  OK- und NOK-Kisten stehen an unterschiedlichen physischen Positionen. Jede Kiste benötigt eine eigene Anfahrts-Sequenz (über Box → Drop → Exit), da Hindernisse oder der Arbeitsbereich des Roboters unterschiedliche Pfade erfordern. Durch separate Konfiguration ist dies flexibel änderbar.

---

## Iteration 7 – Kameragehäusekonzept & 3D-Modell

### Arbeitsschritte

1. **Anforderungen definiert:**
   - Feste Kameraposition relativ zum Roboter für reproduzierbare Bilder.
   - Gleichmäßige Ausleuchtung (LED-Ring) zur Vermeidung von Schattenwurf.
   - Reflexionsarme Oberfläche (schwarzes Material).
   - Kabelführung für Kamerakabel.
   - Stabile Montage ohne Vibration.
2. **Konzeptskizze erstellt:** Zwei-Komponenten-Design: Basis-Plattform mit integrierter Kabelführung + verstellbare Kamera-Halterung.
3. **3D-Modell in Autodesk Fusion 360:**
   - Basis: 200×200 mm Plattform, 10 mm Dicke, Montage-Löcher für M4-Schrauben.
   - Kamera-Arm: Verstellbarer Winkel (30–45°), Höhe 20–30 cm über Würfelposition.
   - LED-Ring-Halterung: Ringförmige Aufnahme um die Kameralinse.
   - STL-Export für den 3D-Druck vorbereitet.

### Entscheidungspunkte

- **Warum ein eigenes Gehäuse statt kommerzielle Halterung?**  
  Kommerzielle Halterungen passen nicht exakt zur Geometrie des Niryo-Roboters und der Kiste-Anordnung. Ein Eigendesign erlaubt die präzise Ausrichtung der Kamera auf die Inspektionsposition und die Integration des LED-Rings in einem Bauteil.

- **Warum PLA/PETG statt Metall?**  
  Der 3D-Druck erlaubt schnelle Design-Iterationen. Anpassungen am Winkel oder an der Kabelführung können innerhalb eines Tages umgesetzt werden. Für eine stationäre Indoor-Anwendung ist die mechanische Belastbarkeit von PLA/PETG ausreichend.

- **Warum schwarzes Material?**  
  Schwarz reduziert Reflexionen, die die Farberkennung (HSV-Filter) stören könnten. Eine reflexionsarme Umgebung verbessert die Erkennungsrate des orangen Würfels erheblich.

---

## Iteration 8 – Kameragehäuse Drucken & Montage

### Arbeitsschritte

1. **Slicing (Druckvorbereitung):**
   - Layer Height: 0.2 mm (Kompromiss aus Druckzeit und Oberflächenqualität).
   - Infill: 20 % für die Basis (leicht, stabil), 40 % für den Kamera-Arm (höhere Steifigkeit).
   - Support-Strukturen für den Kamera-Arm aktiviert.
2. **Prototyp-Druck:** Erster Druck zur Passungsprüfung (Kamera-Aufnahme, LED-Ring, Schraubenlöcher).
3. **Nachbearbeitung:** Support-Material entfernt, Kanten geglättet, Schraubenlöcher nachgebohrt.
4. **Design-Iteration:** Anpassungen am 3D-Modell basierend auf Prototyp-Ergebnis (z. B. Toleranzen für Kamera-Clip korrigiert).
5. **Finaler Druck:** Druckzeit ca. 8–10 h.
6. **Montage & Ausrichtung:**
   - Gehäuse am Arbeitsplatz befestigt.
   - Kamera eingesetzt und fixiert.
   - LED-Ring montiert und verkabelt.
   - Kamerawinkel auf Inspektionsposition ausgerichtet.
   - Testbilder aufgenommen und Bildqualität geprüft.

### Entscheidungspunkte

- **Warum 0.2 mm Layer Height?**  
  0.1 mm hätte die Druckzeit verdoppelt, ohne sichtbaren Vorteil für die Funktionalität. 0.3 mm wäre schneller, aber die Support-Kontaktflächen wären ungenauer.

- **Warum zuerst ein Prototyp?**  
  Passungstoleranzen lassen sich am CAD-Modell nur bedingt validieren. Ein schneller Prototyp-Druck (mit reduzierter Qualität) zeigt binnen weniger Stunden, ob Kamera-Clip, LED-Ring-Aufnahme und Schraubenlöcher passen. Das spart Filament und Zeit für den finalen Druck.

---

## Iteration 9 – Integration & End-to-End

### Arbeitsschritte

1. **Modulzusammenführung:** Alle Schichten (API → Anwendungslogik → Roboter/Vision/DB) zum ersten Mal im Zusammenspiel getestet. Imports und Abhängigkeiten geprüft.
2. **`main.py` als Einstiegspunkt:** FastAPI-App erstellt, DB-Tabellen beim Start via `Base.metadata.create_all()` erzeugt, API- und Dashboard-Router eingebunden, CORS-Middleware für Cross-Origin-Zugriffe konfiguriert.
3. **Deployment auf Roboter:**
   - Code per SCP/Git auf den Niryo-Roboter übertragen.
   - Virtual Environment erstellt, Dependencies installiert.
   - `robot_config.json` auf `127.0.0.1` umgestellt (lokaler Betrieb).
   - `db_config.json` auf absoluten Pfad umgestellt.
   - systemd-Service eingerichtet für automatischen Start.
4. **End-to-End Tests:** Mehrere Würfel nacheinander durch den kompletten Ablauf geschickt (API-Aufruf → Roboter greift → Kamera fotografiert → Erkennung → Vergleich → Sortierung).
5. **Fehlerbehandlung gehärtet:**
   - Roboter nicht erreichbar → Inspektion wird mit `is_ok = False` gespeichert, kein Absturz.
   - Kamera liefert kein Bild → Seite wird als `None` gespeichert, nächste Seite wird trotzdem fotografiert.
   - Greifer greift ins Leere → Warnung geloggt, Sequenz wird fortgesetzt.
   - Unerwartete Exception → wird gefangen, geloggt und sauber abgeschlossen (`finally: controller.disconnect()`).

### Entscheidungspunkte

- **Warum `Base.metadata.create_all()` statt Alembic-Migrationen?**  
  Das System hat ein stabiles, kleines Schema (3 Tabellen). Migrationen sind für Produktionssysteme mit Schema-Evolution sinnvoll. Für dieses dedizierte Inspektionssystem reicht `create_all()` – es erstellt fehlende Tabellen automatisch und ist ein Einzeiler.

- **Warum systemd statt Docker?**  
  Der Niryo-Roboter hat ein Linux-System mit eingeschränkten Ressourcen. Docker hätte einen zusätzlichen Overhead erzeugt (Daemon, Image-Verwaltung). Ein systemd-Service ist leichtgewichtig, startet automatisch nach einem Stromausfall und lässt sich mit Standard-Linux-Tools überwachen.

- **Warum CORS-Middleware mit `allow_origins=["*"]`?**  
  Das Dashboard und externe Clients (z. B. ein Tablet am Arbeitsplatz) greifen über verschiedene IPs auf die API zu. Eine restriktive CORS-Policy hätte den Zugriff unnötig erschwert. Da das System in einem geschlossenen Netzwerk läuft, ist das Sicherheitsrisiko vertretbar.

---

## Iteration 10 – Dokumentation & Abschluss

### Arbeitsschritte

1. **README.md finalisiert:** Vollständige Dokumentation aller Module, des Inspektionsablaufs, des Datenmodells, der API-Endpunkte und der Roboter-Konfiguration.
2. **DEPLOYMENT.md erstellt:** Schritt-für-Schritt-Anleitung für das Deployment auf dem Niryo-Roboter (SSH, Dependencies, Config, systemd-Service) inkl. Troubleshooting-Abschnitt.
3. **Dashboard erweitert:**
   - Tab 1: Healthcheck, letzte Inspektion mit Seitenbildern, Robot-Config-Editor.
   - Tab 2: System-Logs mit Stat-Karten, Balkendiagramm (Logs pro Modul), Filter (Modul, Level, Freitext) und farbiger Log-Tabelle.
   - DB-Explorer: Tabellenübersicht, paginierte Datenansicht, Lösch-Funktionen.
   - Inspektionshistorie: Grafische Darstellung der letzten Ergebnisse.
4. **Projektplan und Spiralmodell-Dokumentation:** Gantt-Diagramm, Meilensteine, Risikoanalyse und Erfolgs-Kriterien erstellt.
5. **Abschlusstests:** Finaler End-to-End-Durchlauf, alle Endpunkte getestet, Dashboard-Funktionalität verifiziert.

### Entscheidungspunkte

- **Warum ein eingebettetes Dashboard statt separatem Frontend?**  
  Ein separates Frontend (z. B. React-App) hätte einen eigenen Build-Prozess und ein eigenes Deployment erfordert. Eine einzelne `dashboard.html`-Datei, die vom FastAPI-Server ausgeliefert wird, ist einfacher zu deployen und zu warten. Alle API-Calls gehen an denselben Server – kein CORS-Setup zwischen Frontend und Backend nötig.

- **Warum Dashboard als optionaler Baustein?**  
  Das Dashboard ist unter `/dashboard/` gemountet und hat keine Abhängigkeiten zur Kernlogik. Es kann komplett entfernt werden, ohne die Inspektion zu beeinflussen. Diese Entkopplung erlaubt es, das Dashboard bei Ressourcenknappheit zu deaktivieren oder durch eine andere Oberfläche zu ersetzen.

---

## Zusammenfassung der Architekturentscheidungen

| Entscheidung | Begründung |
|---|---|
| Modulare Schichtenarchitektur | Klare Trennung von API, Logik und Infrastruktur → wartbar, testbar |
| Externe JSON-Konfiguration | Roboterpositionen änderbar ohne Code-Anpassung → flexibel |
| Repository-Pattern | Datenzugriff gekapselt → austauschbar, testbar |
| Background-Tasks | Inspektion blockiert nicht den API-Aufruf → bessere UX |
| SQLite (dateibasiert) | Kein separater DB-Server nötig → ideal für Embedded-Betrieb |
| HSV-Farbraum + Contour-Hierarchie | Robust gegen Beleuchtungsschwankungen → zuverlässige Erkennung |
| Zentrales DB-Logging | Logs im Dashboard filterbar → bessere Betriebsüberwachung |
| systemd-Deployment | Leichtgewichtig, Auto-Start → produktionstauglich |
