# 5. Projektergebnisse

## 5.1 Gesamtergebnis

Das Cube Inspection System ist ein funktionsfähiges Qualitätsprüfsystem, das einen Niryo-Roboter, eine Kamera und eine Bildverarbeitungspipeline zu einem automatisierten Inspektionsablauf kombiniert. Das System nimmt über eine REST-API Soll-Konfigurationen entgegen, führt die Inspektion als Background-Task durch und sortiert den Würfel anschließend in die passende Kiste (i.O. / n.i.O.).

## 5.2 Dokumentation der Testphase

### 5.2.1 Testübersicht

Die Tests wurden iterativ durchgeführt und decken vier Bereiche ab:

| Bereich | Testskript | Testart | Umgebung |
|---------|-----------|---------|----------|
| Roboter-Bewegung | `test_robot.py` | Integrationstest | Roboter (physisch) |
| Kamera-Anbindung | `test_cameraConnection.py` | Verbindungstest | Roboter (physisch) |
| Bildverarbeitung (Roboter) | `test_vision.py` | Integrationstest | Roboter (physisch) |
| Bildverarbeitung (USB) | `test_vision_usb.py` | Isolierter Test | Entwicklungs-PC |
| Greifer-Sequenz | `test_gripper.py` | End-to-End-Test | Roboter (physisch) |
| Neue Sequenz + Safety | `test_new_sequence.py` | End-to-End-Test | Roboter (physisch) |
| REST-API | `test_api.py` | Integrationstest | Lokal (HTTP) |

### 5.2.2 Roboter-Bewegungstest (`test_robot.py`)

**Ziel:** Grundlegende Robotersteuerung und Sequenzfahrt validieren.

**Ablauf:** Der Roboter verbindet sich über `NiryoRobot("10.10.10.10")`, prüft den Kalibrierungsstatus und fährt sechs vordefinierte Gelenkpositionen (`POS_1` bis `POS_6`) nacheinander ab. An Position 1 wird der Greifer geschlossen, an Position 6 geöffnet. Abschließend fährt der Roboter in die Home-Position. Nach der Roboter-Sequenz wird automatisch `test_vision.py` gestartet.

**Ergebnis:** Alle Positionen werden kollisionsfrei angefahren, Greifer öffnet und schließt zuverlässig.

### 5.2.3 Kamera-Verbindungstest (`test_cameraConnection.py`)

**Ziel:** Prüfen, ob die Kamera über die Niryo-API Bilder liefert.

**Ablauf:** Über `robot.get_img_compressed()` wird ein komprimiertes Bild abgerufen und mit `cv2.imdecode()` manuell dekodiert (kompatibel mit numpy 2.x). Das Bild wird in einem OpenCV-Fenster angezeigt.

**Ergebnis:** Kamera liefert Bilder über die Roboter-API. Die manuelle Dekodierung mit `np.frombuffer()` ist notwendig, da die Standard-Dekodierung von pyniryo mit neueren numpy-Versionen inkompatibel ist.

### 5.2.4 Bildverarbeitungstest – Roboter-Kamera (`test_vision.py`)

**Ziel:** Würfelerkennung und Augenzählung mit der echten Roboter-Kamera validieren.

**Ablauf:** Das Skript zeigt ein Livebild der Roboter-Kamera in einem OpenCV-Fenster mit interaktiven Buttons (Analysieren / Beenden). Bei Klick auf "Analysieren" wird `detect_cube(img, color, debug=True)` aufgerufen. Die Erkennung nutzt HSV-Farbfilterung, Konturerkennung und Zirkularitätsprüfung. Pro Analyse werden fünf Bilder gespeichert:

- `01_raw.jpg` – Rohbild
- `02_result.jpg` – Ergebnis mit Bounding-Box und Augenzahl
- `03_mask.jpg` – Farbmaske
- `04_dark_spots.jpg` – Maske der erkannten Augen (dunkle Punkte)
- `05_roi.jpg` – Ausgeschnittener Würfelbereich (Region of Interest)

**Besonderheit:** Das Kamerabild wird um 180° gedreht (`cv2.ROTATE_180`), da die Kamera in der Fotobox auf dem Kopf montiert ist.

**Ergebnis:** Augenzahlen 1–6 werden bei ausreichender Beleuchtung zuverlässig erkannt.

### 5.2.5 Bildverarbeitungstest – USB-Kamera (`test_vision_usb.py`)

**Ziel:** Bildverarbeitungslogik isoliert vom Roboter testen, um OpenCV-Parameter iterativ anpassen zu können.

**Hintergrund:** Um die Erkennungslogik auch ohne Zugang zum physischen Roboter weiterentwickeln zu können, wurde `test_vision_usb.py` erstellt. Das Skript nutzt eine direkt per USB angeschlossene Kamera am Entwicklungs-PC.

**Technische Umsetzung:**
- Die Kamera wird über `cv2.VideoCapture(CAMERA_INDEX)` angesprochen (Index konfigurierbar, z.B. 0 = Elgato, 1 = Logitech)
- `detection.py` und `image_processing.py` werden per `importlib.util` direkt geladen, um den Import von `pyniryo` zu umgehen – so läuft der Test auf jedem PC ohne Roboter-SDK
- Die automatische Farberkennung (`COLOR = "auto"`) wurde hier entwickelt und getestet
- Zusätzlich zu den fünf Debug-Bildern wird ein **Composite-Bild** (`06_composite.jpg`) generiert, das Ergebnis, Maske und ROI nebeneinander darstellt – inklusive Info-Leiste mit erkannter Augenzahl und Farbquadrat

**Ergebnis:** Die iterative Anpassung der OpenCV-Parameter (HSV-Farbbereiche, Schwellwerte für `MIN_CUBE_AREA`, `MIN_DOT_AREA`, `MIN_CIRCULARITY`) konnte so ohne physischen Roboter durchgeführt werden. Die Composite-Ansicht erleichterte die visuelle Bewertung der Erkennungsqualität erheblich.

### 5.2.6 Greifer-Sequenz & End-to-End-Test (`test_gripper.py`)

**Ziel:** Komplette Pick-Inspect-Sort-Sequenz mit Würfelerkennung und Sortierung testen.

**Ablauf (16 Schritte):**

| Phase | Schritte | Beschreibung |
|-------|----------|--------------|
| Pick | 1–3 | Über Würfel fahren, positionieren, Greifer schließen |
| Transport | 4–7 | Hoch fahren, zur Kamera-Box fahren, Eingang Kamera-Gehäuse, vor Kamera positionieren |
| Inspektion | 8–9 | Foto Seite 1 aufnehmen, Greifer um ca. 140° rotieren, Foto Seite 2 aufnehmen |
| Rückfahrt | 10–11 | Aus Kamera-Gehäuse fahren, über Sortierboxen positionieren |
| Sortierung | 12–16 | Je nach Ergebnis OK- oder NOK-Pfad anfahren, Greifer öffnen, Home |

**Fehlerbehandlung:** Jede Bewegung wird über `safe_move()` ausgeführt, das nach jeder Fahrt den Kollisionsstatus prüft. Bei Fehler wird ein Notfall-Stopp ausgelöst (Learning Mode kurz an/aus um Bewegung zu stoppen, Gelenke bleiben gesperrt).

**Ergebnis:** Die komplette Sequenz läuft in ca. 30–60 Sekunden durch. Beide Würfelseiten werden erkannt und die Sortierung erfolgt korrekt in die jeweilige Box.

### 5.2.7 Sequenz mit Safety-System (`test_new_sequence.py`)

**Ziel:** Erweiterte Sequenz mit konfigurierbarem Safety-System testen.

**Unterschied zu `test_gripper.py`:** Die Sequenz wird als deklarative Aktionsliste definiert (`"move"`, `"open"`, `"close"`, `"home"`), nicht als hartkodierte Schritte. Safety-Parameter werden aus `robot_config.json` geladen:

| Parameter | Wert | Beschreibung |
|-----------|------|--------------|
| `arm_max_velocity` | 80% | Maximale Armgeschwindigkeit |
| `grip_loss_threshold` | 0.005 rad | Maximale Gelenkabweichung für Greifprüfung |
| `gripper_max_torque_percentage` | 100% | Maximales Greifer-Drehmoment |
| `grip_check_wait_sec` | 0.2s | Wartezeit nach Nachgreifen |
| `led_error_color` | [255, 0, 0] | LED-Farbe bei Fehler (rot) |
| `led_ok_color` | [0, 255, 0] | LED-Farbe bei Erfolg (grün) |

**Grip-Loss-Erkennung:** Nach jeder Bewegung mit geschlossenem Greifer wird nachgegriffen und die Gelenkpositionen vorher/nachher verglichen. Weicht ein Gelenk um mehr als `grip_loss_threshold` ab, wird Würfelverlust erkannt und ein Notfall-Stopp ausgelöst (LED rot, Greifer auf, Motoren halten).

**Ergebnis:** Das Safety-System erkennt Würfelverlust und Kollisionen zuverlässig. Die LED-Signalisierung (grün bei Erfolg, rot bei Fehler) gibt klares visuelles Feedback.

### 5.2.8 API-Test (`test_api.py`)

**Ziel:** Alle REST-API-Endpunkte auf Erreichbarkeit und korrekte Antworten prüfen.

**Getestete Endpunkte:**

| Test | Endpunkt | Prüfung |
|------|----------|---------|
| `test_health_check()` | `GET /` | Server erreichbar, Status 200 |
| `test_create_configuration()` | `POST /api/config` | Soll-Konfiguration wird gespeichert |
| `test_get_inspections()` | `GET /api/inspections` | Prüfergebnisse werden korrekt zurückgegeben |
| `test_system_healthcheck()` | `GET /api/healthcheck` | Komponentenstatus (Roboter, Kalibrierung, Kamera) |
| `test_calibration()` | `POST /api/calibration` | Automatische Kalibrierung wird ausgelöst |

**Ablauf:** Das Skript sendet sequentiell HTTP-Requests an den laufenden FastAPI-Server (`http://127.0.0.1:8000`) über die `requests`-Bibliothek. Jeder Test gibt Status und Antwort auf der Konsole aus.

**Ergebnis:** Alle Endpunkte antworten mit Status 200. Die Soll-Konfiguration wird korrekt in der Datenbank gespeichert und die Inspektion als Background-Task gestartet.

---

## 5.3 Ergebnisübersicht nach Komponente

### 5.3.1 REST-API (FastAPI)

- 6 API-Endpunkte unter `/api` implementiert (siehe Iteration 4)
- Eingabevalidierung über Pydantic-Schemas (`ConfigurationCreate`, `InspectionResponse`)
- Inspektionen laufen als `BackgroundTasks`, Client wird nicht blockiert
- CORS-Middleware aktiviert für Cross-Origin-Zugriffe

### 5.3.2 Robotersteuerung

- Alle Positionen in `robot_config.json` ausgelagert (10 Sequenz-Positionen + 6 Sortierpositionen)
- Greifer-Geschwindigkeit: 500, maximale Armgeschwindigkeit: 80%
- Safety-System mit Kollisionserkennung und Grip-Loss-Erkennung
- LED-Feedback: Grün bei Erfolg, Rot bei Fehler
- Notfall-Stopp: LED bleibt rot, Motoren bleiben aktiv, Verbindung bleibt offen

### 5.3.3 Bildverarbeitung (OpenCV)

- HSV-Farbfilterung mit konfigurierbaren Farbbereichen (`COLOR_RANGES`)
- Automatische Farberkennung (`color = "auto"`)
- Konturerkennung mit Schwellwerten: `MIN_CUBE_AREA = 2000`, `MIN_DOT_AREA = 30–800`, `MIN_CIRCULARITY = 0.45`
- Pro Inspektion: 2 Aufnahmen (Seite 1 + Seite 2 nach Greifer-Rotation)
- Rohbilder und annotierte Ergebnisbilder werden gespeichert

### 5.3.4 Datenbank (SQLite + SQLAlchemy)

Drei Tabellen:

| Tabelle | Zweck | Felder (Auswahl) |
|---------|-------|-------------------|
| `configurations` | Soll-Konfigurationen | `target_color_left`, `target_color_right`, `target_dots` (JSON-String) |
| `inspections` | Prüfergebnisse | `actual_dots`, `is_ok`, `confidence`, `timestamp` |
| `system_logs` | System-Logging | `module`, `level`, `message`, `timestamp` |

- Repository-Pattern: API-Schicht kennt keine SQL-Queries
- Augenzahlen als JSON-String, da SQLite keine nativen Arrays unterstützt
- `system_logs` ohne Fremdschlüssel auf `inspections` (Logs auch ohne Inspektionskontext möglich)
- Log-Rotation: Daemon-Thread löscht täglich Einträge älter als 30 Tage

### 5.3.5 Dashboard (Demo)

Ein Demo-Dashboard unter `/dashboard` bietet:
- Anzeige der letzten Inspektion mit SOLL/IST-Vergleich und Seitenbildern
- Inspektions-Historie als Grafik
- System-Logs mit Filter nach Modul und Level
- Datenbank-Browser mit Tabellen-Übersicht und Einzel-Löschung
- Robot-Config-Editor zum Lesen und Schreiben der `robot_config.json`

Das Dashboard ist als reine HTML-Seite implementiert und nicht Teil der Kern-API – es kann entfernt werden, ohne die Inspektion zu beeinflussen.

## 5.4 Bekannte Einschränkungen

- **Kein finales PAUL-Format:** Die Soll-Konfiguration wird aktuell über die eigene REST-API übergeben. Das JSON-Schema ist anpassbar, sobald PAUL ein finales Format bereitstellt.
- **Beleuchtungsabhängigkeit:** Die Augenerkennung funktioniert zuverlässig bei gleichmäßiger Beleuchtung in der Fotobox. Starke Schattenwürfe oder Reflexionen können die Erkennung beeinträchtigen.
- **Zwei Würfelseiten:** Aktuell werden zwei Seiten geprüft (Seite 1 + rotierte Seite 2). Eine Erweiterung auf weitere Seiten erfordert zusätzliche Kamerapositionen in der Sequenz.
