# Cube Inspection System – PAULQS

Automatisierte Qualitaetspruefung von Wuerfeln mit einem **Niryo-Roboterarm**, einer **Kamera** und **Computer Vision (OpenCV)**. Der Roboter greift einen Wuerfel, positioniert ihn vor der Kamera, erkennt die Augenzahl auf mehreren Seiten und vergleicht das Ergebnis mit einer Soll-Konfiguration. Anschliessend sortiert der Roboter den Wuerfel in die richtige Kiste (korrekt / fehlerhaft).

---

## Inhaltsverzeichnis

1. [Architektur](#architektur)
2. [Projektstruktur](#projektstruktur)
3. [Technologie-Stack](#technologie-stack)
4. [Kompletter Inspektionsablauf](#kompletter-inspektionsablauf)
5. [Module im Detail](#module-im-detail)
6. [Datenmodell](#datenmodell)
7. [API-Endpunkte](#api-endpunkte)
8. [Roboter-Konfiguration (Deep Dive)](#roboter-konfiguration-deep-dive)
9. [Neue Sequenzen einrichten](#neue-sequenzen-einrichten)
10. [Installation & Start](#installation--start)
11. [Testen](#testen)

---

## Architektur

Das System folgt einer **modularen Schichtenarchitektur**:

```
┌─────────────────────────────────────────────────┐
│                   API-Schicht                    │
│   routes.py · schemas.py · dependencies.py       │
├─────────────────────────────────────────────────┤
│                Anwendungsschicht                 │
│   inspection_service.py · sorting_service.py     │
├──────────┬──────────────┬───────────────────────┤
│  Roboter │    Vision    │      Datenbank        │
│controller│  camera.py   │   db.py + models.py   │
│movements │  detection   │   repository.py       │
│  config  │  processing  │   db_config.json      │
└──────────┴──────────────┴───────────────────────┘
```

**Prinzipien:**
- Jedes Modul hat **eine klare Aufgabe**
- Konfiguration ist **extern** (JSON-Dateien), nicht im Code
- Datenbankzugriffe laufen ueber ein **Repository-Pattern**
- Roboter-Positionen sind **frei konfigurierbar** ohne Code-Aenderungen

---

## Projektstruktur

```
cube-inspection-system/
├── app/
│   ├── main.py                          # FastAPI-Einstiegspunkt, startet Server
│   ├── config.py                        # Globale Konfiguration (reserviert)
│   │
│   ├── api/                             # --- API-Schicht ---
│   │   ├── routes.py                    # REST-Endpunkte (/config, /inspections, /healthcheck)
│   │   ├── schemas.py                   # Pydantic-Schemas (Request/Response Validierung)
│   │   └── dependencies.py              # DB-Session Dependency (get_db)
│   │
│   ├── application/                     # --- Anwendungslogik ---
│   │   ├── inspection_service.py        # Orchestriert: Robot → Kamera → Erkennung → Vergleich → DB
│   │   └── sorting_service.py           # Wuerfel in Kiste sortieren (OK / NOK)
│   │
│   ├── dashboard/                       # --- Demo-Dashboard ---
│   │   ├── routes.py                    # Dashboard-API (Bilder, Config, Inspektion, System Logs)
│   │   └── dashboard.html               # Web-Oberflaeche mit Tab-Navigation (Config + Logs)
│   │
│   ├── infrastructure/                  # --- Externe Systeme ---
│   │   ├── database/
│   │   │   ├── db.py                    # SQLAlchemy Engine + Session
│   │   │   ├── db_config.json           # Datenbank-Verbindung (SQLite-Pfad)
│   │   │   ├── models.py               # SQLAlchemy-Tabellen (Configuration, Inspection, SystemLog)
│   │   │   └── repository.py            # CRUD-Operationen (Repository-Pattern)
│   │   │
│   │   ├── robot/
│   │   │   ├── robot_controller.py      # Roboter-Steuerung (connect, move, grip mit Retry, sequence)
│   │   │   ├── movements.py             # Liest robot_config.json, stellt Hilfsfunktionen bereit
│   │   │   └── robot_config.json        # *** WICHTIG: Alle Positionen + Sequenz + IP + Sortier-Positionen ***
│   │   │
│   │   └── vision/
│   │       ├── camera.py                # Bildaufnahme von Roboter-Kamera (1 Funktion)
│   │       ├── image_processing.py      # Farbmasken (Orange-Filter) + Schwellwert
│   │       ├── detection.py             # Wuerfelerkennung + Augenzaehlung
│   │       └── captures/                # Gespeicherte Bilder (side_1_raw.jpg, side_1_result.jpg, ...)
│   │
│   └── utils/                           # --- Hilfsfunktionen ---
│       ├── logger.py                    # Zentrales Logging-System (schreibt in system_logs DB)
│       └── helpers.py                   # Allgemeine Hilfsfunktionen (reserviert)
│
├── tests/                               # --- Tests ---
│   ├── test_api.py                      # API-Endpunkt Tests
│   ├── test_robot.py                    # Roboter-Steuerung Tests
│   ├── test_vision.py                   # Vision/Erkennung Tests (Live-Stream)
│   ├── test_gripper.py                  # Greifer Tests
│   ├── test_cameraConnection.py         # Kamera-Verbindung Tests
│   ├── test_comparison.py               # Vergleichslogik Tests
│   └── test_images/                     # Testbilder
│
├── requirements.txt                     # Python-Abhaengigkeiten
└── test.db                              # SQLite-Datenbank (wird automatisch erstellt)
```

---

## Technologie-Stack

| Bereich | Technologie | Zweck |
|---------|-------------|-------|
| **Web-Framework** | FastAPI | REST-API, async Background-Tasks |
| **Server** | Uvicorn | ASGI-Server fuer FastAPI |
| **Datenbank** | SQLite + SQLAlchemy | Persistenz, ORM |
| **Validierung** | Pydantic v2 | Request/Response-Schemas |
| **Computer Vision** | OpenCV (cv2) | Bilderkennung, Farbfilter |
| **Bildverarbeitung** | NumPy | Array-Operationen fuer Bilder |
| **Roboter-SDK** | pyniryo | Niryo-Roboter-Steuerung |
| **Sprache** | Python 3.12+ | Type Hints, Union-Syntax |

---

## Kompletter Inspektionsablauf

Der gesamte Flow wird durch `POST /api/config` ausgeloest:

```
┌──────────────────────────────────────────────────────────────┐
│  1. API empfaengt Soll-Konfiguration (POST /api/config)      │
│     → Speichert in DB-Tabelle "configurations"               │
│     → Startet Background-Task: run_inspection(config_id)     │
│     → Log: "Neue Konfiguration empfangen (ID: X)"            │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  2. Roboter verbinden + vorbereiten                          │
│     → controller.connect()  (IP aus robot_config.json)       │
│     → controller.prepare()  (Kalibrierung pruefen)           │
│     → Log: "Verbunden mit Roboter (10.10.10.10)"            │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  3. Roboter-Sequenz abfahren (step1 → step9)                │
│     → step1: Greifer oeffnen                                 │
│     → step2: Zur Aufnahmeposition fahren                     │
│     → step3: Greifer schliessen (Wuerfel greifen)            │
│       ├─ Greifer-Position pruefen (0-1000)                   │
│       ├─ Position > 200 = Wuerfel gegriffen ✓                │
│       └─ Position ≤ 200 = Retry (max. 3 Versuche)            │
│     → step4-step6: Wuerfel vor Kamera positionieren          │
│     → step7: Kamera-Aufnahme Seite 1                        │
│     → step8: Kamera-Aufnahme Seite 2                        │
│     → step9: Kamera-Aufnahme Seite 3                        │
│     → Home-Position                                          │
│     → Log: "Sequenz abgeschlossen, 3 Bilder aufgenommen"     │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  4. Bildanalyse (pro aufgenommenem Bild)                     │
│     → get_orange_mask()  → Wuerfel lokalisieren (HSV-Filter) │
│     → findContours()     → Groesste Kontur = Wuerfel         │
│     → get_dark_spots()   → Dunkle Punkte = Augen             │
│     → detect_cube()      → {"dots": 3, "x":..., "y":...}    │
│     → Bilder speichern   → side_1_raw.jpg + side_1_result.jpg│
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  5. Soll/Ist-Vergleich                                       │
│     → Soll: config.target_dots aus DB   z.B. [1, 3, 5]      │
│     → Ist:  erkannte Augenzahlen        z.B. [5, 1, 3]      │
│     → Vergleich: sorted(Soll) == sorted(Ist)                │
│     → Reihenfolge egal! Nur die Werte muessen stimmen        │
│     → is_ok = True/False                                     │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  6. Ergebnis in DB speichern                                 │
│     → Tabelle "inspections" (actual_dots, is_ok)             │
│     → Log: "Ergebnis: Soll=[1,3,5], Ist=[3,5,1], OK=True"   │
└──────────────────────┬───────────────────────────────────────┘
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  7. Wuerfel sortieren (sorting_service.py)                   │
│     → is_ok = True  → Roboter faehrt zu Position "sort_ok"  │
│     → is_ok = False → Roboter faehrt zu Position "sort_nok"  │
│     → Greifer oeffnen → Wuerfel in Kiste ablegen             │
│     → Log: "Wuerfel abgelegt bei Position 'sort_ok'"         │
└──────────────────────────────────────────────────────────────┘

**Hinweis:** Alle Schritte werden ins System-Log geschrieben und koennen
im Dashboard unter "System Logs" eingesehen werden.
```

---

## Module im Detail

### `main.py` – Einstiegspunkt

Startet die FastAPI-App, erstellt DB-Tabellen und bindet alle Routen ein:
- `/api/...` → API-Endpunkte (routes.py)
- `/dashboard/...` → Demo-Dashboard (dashboard/routes.py)

### `api/routes.py` – REST-Endpunkte

| Endpunkt | Methode | Was passiert |
|----------|---------|-------------|
| `/api/config` | POST | Soll-Konfiguration speichern + Inspektion starten |
| `/api/inspections` | GET | Letzte Pruefergebnisse abrufen |
| `/api/healthcheck` | GET | Roboter + Kamera Status pruefen |
| `/api/calibration` | POST | Roboter automatisch kalibrieren |

### `api/schemas.py` – Datenvalidierung

Definiert die Datenstruktur fuer API-Requests und Responses:
- **ConfigurationCreate**: `target_color_left`, `target_color_right`, `target_dots` (Liste)
- **InspectionCreate**: Ergebnis einer Inspektion
- **InspectionResponse**: Antwortformat fuer GET /inspections

### `api/dependencies.py` – Abhaengigkeiten

Stellt die `get_db()` Funktion bereit, die eine Datenbank-Session erzeugt und nach Gebrauch schliesst.

### `application/inspection_service.py` – Hauptlogik

Die zentrale Datei. Orchestriert den gesamten Inspektionsablauf in 6 Schritten:

```python
def run_inspection(config_id):
    # Schritt 1: Roboter verbinden
    # Schritt 2: Roboter vorbereiten
    # Schritt 3: Sequenz fahren + Bilder aufnehmen
    # Schritt 4: Bilder analysieren
    # Schritt 5: Ergebnis in DB speichern
    # Schritt 6: Wuerfel sortieren (OK/NOK Kiste)
```

Hilfsfunktionen:
- `_run_robot_sequence()` – Roboter-Sequenz ausfuehren, Bilder sammeln
- `_analyze_images()` – Jedes Bild durch detect_cube() analysieren + speichern
- `_draw_box()` – Bounding-Box und Augenzahl ins Ergebnisbild zeichnen
- `_save_result()` – Soll/Ist vergleichen und in DB speichern

### `application/sorting_service.py` – Wuerfel-Sortierung

Sortiert den Wuerfel nach dem Inspektionsergebnis in die richtige Kiste:

```python
def sort_cube(controller, is_ok):
    # is_ok = True  → faehrt zu Position "sort_ok"  (Kiste KORREKT)
    # is_ok = False → faehrt zu Position "sort_nok" (Kiste FEHLERHAFT)
    # Greifer oeffnen → Wuerfel ablegen
```

Die Positionen `sort_ok` und `sort_nok` werden aus der `robot_config.json` gelesen.

### `infrastructure/robot/robot_controller.py` – Roboter-Steuerung

Klasse `RobotController`:

| Methode | Was sie macht |
|---------|--------------|
| `connect()` | Verbindet mit Niryo ueber IP aus robot_config.json |
| `disconnect()` | Trennt Verbindung |
| `prepare()` | Prueft Kalibrierung, deaktiviert Learning-Mode |
| `move_to("step3")` | Faehrt zu einer benannten Position (6 Gelenkwinkel) |
| `grip(max_retries=3)` | Greifer schliessen mit Pruefung + Retry-Logik |
| `get_gripper_position()` | Liest aktuelle Greifer-Position (0-1000) |
| `release()` | Greifer oeffnen |
| `go_home()` | Zur Home-Position fahren |
| `run_sequence_with_capture(...)` | Sequenz abfahren, bei bestimmten Steps fotografieren |

**Greifer-Pruefung (NEU):**

Die `grip()` Methode prueft nach dem Schliessen, ob der Wuerfel tatsaechlich gegriffen wurde:

```python
# Greifer-Position auslesen (0 = komplett zu, 1000 = komplett offen)
gripper_pos = self.get_gripper_position()

if gripper_pos > 200:
    # Wuerfel gegriffen 
    return True
else:
    # Nichts gegriffen → Retry (max. 3 Versuche)
    # Greifer oeffnen, 0.5s warten, erneut versuchen
```

**Ablauf bei Fehlschlag:**
1. Versuch 1: Greifer zu → Position ≤ 200 → Log: WARNING
2. Greifer auf, 0.5s warten
3. Versuch 2: Greifer zu → Position ≤ 200 → Log: WARNING
4. Greifer auf, 0.5s warten
5. Versuch 3: Greifer zu → Position ≤ 200 → Log: ERROR
6. **Sequenz wird abgebrochen** (return `[]`)

Die Schwellenwerte sind konfigurierbar (aktuell: 200 fuer "nichts gegriffen").

### `infrastructure/robot/movements.py` – Config-Zugriff

Liest `robot_config.json` und stellt einfache Funktionen bereit:

```python
get_robot_ip()          # → "10.10.10.10"
get_position("step3")   # → [-0.772, -0.793, -0.148, -0.055, -0.499, 0.048]
get_sequence()          # → ["step1", "step2", ..., "step9"]
get_gripper_close_at()  # → "step3"
get_gripper_open_at()   # → "step1"
get_capture_at()        # → ["step7", "step8", "step9"]
get_gripper_speed()     # → 500
```

### `infrastructure/vision/camera.py` – Bildaufnahme

Eine einzige Funktion:

```python
def capture(robot) -> BGR-Bild oder None
```

Ablauf: `robot.get_img_compressed()` → `np.frombuffer()` → `cv2.imdecode()` → BGR-Bild

### `infrastructure/vision/image_processing.py` – Bildverarbeitung

| Funktion | Eingabe | Ausgabe | Zweck |
|----------|---------|---------|-------|
| `get_orange_mask(img)` | BGR-Bild | Binaermaske | Filtert orange Pixel (HSV-Farbraum) |
| `get_dark_spots(gray_roi)` | Graustufen-Bild | Binaermaske | Findet dunkle Punkte (Wuerfelaugen) |

HSV-Grenzen fuer Orange: H=5-25, S=150-255, V=120-255

### `infrastructure/vision/detection.py` – Wuerfelerkennung

```python
def detect_cube(img) -> {"x", "y", "w", "h", "dots"} oder None
```

Ablauf:
1. Orange Maske erstellen → Wuerfel finden
2. Groesste passende Kontur waehlen (Flaeche > 2000px, grob quadratisch)
3. ROI ausschneiden → dunkle Punkte zaehlen
4. Filter: Flaeche 15-500px + Zirkularitaet > 0.35 = echte Augen

### `infrastructure/database/models.py` – Datenbankmodelle

Drei SQLAlchemy-Tabellen: `Configuration`, `Inspection`, `SystemLog`

### `infrastructure/database/repository.py` – Datenbankzugriff

Klasse `InspectionRepository` (Repository-Pattern):

| Methode | Beschreibung |
|---------|-------------|
| `save_config(data)` | Speichert Soll-Konfiguration |
| `save_inspection(data)` | Speichert Pruefergebnis |
| `get_all_inspections(limit)` | Holt die letzten Ergebnisse |

### `utils/logger.py` – Zentrales Logging-System (NEU)

**Eine einfache Funktion fuer System-Logs:**

```python
from app.utils.logger import log

log("ROBOT", "INFO", "Verbunden mit Roboter (10.10.10.10)")
log("VISION", "WARNING", "Seite 2: Kein Bild erhalten")
log("INSPECTION", "ERROR", "Roboter-Verbindung fehlgeschlagen")
```

**Module:** ROBOT, VISION, INSPECTION, SORTING, API, DATABASE  
**Levels:** INFO, WARNING, ERROR

**Funktionsweise:**
- Erstellt automatisch eigene DB-Session (SessionLocal)
- Schreibt in `system_logs` Tabelle
- Printet gleichzeitig in die Konsole
- Kann von ueberall aufgerufen werden (keine Session-Uebergabe noetig)

**Integration:**
- `inspection_service.py` – loggt jeden Schritt der Inspektion
- `sorting_service.py` – loggt Sortier-Entscheidungen
- `robot_controller.py` – loggt Verbindung, Bewegungen, Greifer-Status
- `api/routes.py` – loggt API-Requests (Config, Kalibrierung)

### `dashboard/` – Demo-Dashboard (NEU: mit System Logs Tab)

Web-Oberflaeche zum Testen. Kann komplett entfernt werden, ohne die Inspektion zu beeinflussen.

**Tab 1: Dashboard**
- Healthcheck (Roboter, Kalibrierung, Kamera)
- Letzte Inspektion (Ergebnis, Bilder pro Seite)
- Robot-Config Editor (Positionen, Sequenz, Drag & Drop)

**Tab 2: System Logs (NEU)**
- **4 Stat-Karten:** Gesamt, Info, Warnings, Errors
- **Balkendiagramm:** Logs pro Modul (gestapelt: Info/Warning/Error)
- **Filter:**
  - Modul (ROBOT, VISION, INSPECTION, SORTING, API, DATABASE)
  - Level (INFO, WARNING, ERROR)
  - Freitext-Suche in Nachricht
- **Log-Tabelle:** Zeitpunkt, Modul (farbig), Level (farbig mit Icons), Nachricht

**Erreichbar unter:** `/dashboard/`

---

## Datenmodell

### `configurations` – Soll-Konfiguration
| Spalte | Typ | Beschreibung |
|--------|-----|-------------|
| id | Integer (PK) | Auto-Inkrement |
| target_color_left | String | Soll-Farbe links |
| target_color_right | String | Soll-Farbe rechts |
| target_dots | String (JSON) | Soll-Augenzahlen als JSON-Liste, z.B. `"[1, 3, 5]"` |
| created_at | DateTime | Erstellzeitpunkt |

### `inspections` – Pruefergebnisse
| Spalte | Typ | Beschreibung |
|--------|-----|-------------|
| id | Integer (PK) | Auto-Inkrement |
| config_id | Integer (FK) | Verweis auf Configuration |
| timestamp | DateTime | Pruefzeitpunkt |
| actual_color_left | String | Erkannte Farbe links |
| actual_color_right | String | Erkannte Farbe rechts |
| actual_dots | String (JSON) | Erkannte Augenzahlen als JSON-Liste |
| confidence | Float | Erkennungssicherheit (0.0 - 1.0) |
| is_ok | Boolean | Soll == Ist? (reihenfolge-unabhaengig) |

### `system_logs` – Systemprotokoll (NEU)
| Spalte | Typ | Beschreibung |
|--------|-----|-------------|
| id | Integer (PK) | Auto-Inkrement |
| module | String | Modul (ROBOT, VISION, INSPECTION, SORTING, API, DATABASE) |
| level | String | Level (INFO, WARNING, ERROR) |
| message | String | Log-Nachricht |
| timestamp | DateTime | Zeitpunkt (UTC)

**Beispiel-Eintraege:**

| module | level | message | timestamp |
|--------|-------|---------|----------|
| API | INFO | Neue Konfiguration empfangen (ID: 5, Soll: [1, 3, 5]) | 2026-03-22 14:30:00 |
| ROBOT | INFO | Verbunden mit Roboter (10.10.10.10) | 2026-03-22 14:30:01 |
| ROBOT | INFO | Greifer schliessen bei step3 | 2026-03-22 14:30:05 |
| ROBOT | WARNING | Versuch 1/3: Kein Wuerfel gegriffen (Position: 150) | 2026-03-22 14:30:05 |
| ROBOT | INFO | Wuerfel gegriffen (Greifer-Position: 480) | 2026-03-22 14:30:06 |
| VISION | INFO | Seite 1 (step7): 3 Augen erkannt | 2026-03-22 14:30:10 |
| INSPECTION | INFO | Ergebnis: Soll=[1, 3, 5], Ist=[3, 5, 1], OK=True | 2026-03-22 14:30:15 |
| SORTING | INFO | Wuerfel ist OK → Kiste KORREKT | 2026-03-22 14:30:15 |
| SORTING | INFO | Wuerfel abgelegt bei Position 'sort_ok' | 2026-03-22 14:30:17 |

---

## API-Endpunkte

### Uebersicht

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| `GET` | `/` | Systemstatus |
| `POST` | `/api/config` | Soll-Werte senden → startet Inspektion |
| `GET` | `/api/inspections` | Pruefergebnisse abrufen |
| `GET` | `/api/healthcheck` | Robot + Kamera Status |
| `POST` | `/api/calibration` | Roboter kalibrieren |
| `GET` | `/dashboard/` | Web-Dashboard |
| `GET` | `/dashboard/robot-config` | Robot-Config lesen |
| `PUT` | `/dashboard/robot-config` | Robot-Config schreiben |
| `GET` | `/dashboard/last-inspection` | Letzte Inspektion + Bilder |
| `GET` | `/dashboard/side-image/{side}/{type}` | Einzelnes Seitenbild |
| `GET` | `/dashboard/system-logs` | System-Logs (optional: ?module=ROBOT&level=ERROR&limit=500) |

### Beispiel: Inspektion ausloesen

```bash
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "target_color_left": "orange",
    "target_color_right": "orange",
    "target_dots": [1, 3, 5]
  }'
```

### Beispiel: Ergebnisse abrufen

```bash
curl http://localhost:8000/api/inspections
```

```json
[
  {
    "id": 1,
    "config_id": 1,
    "timestamp": "2026-03-22T12:30:00",
    "actual_dots": [5, 1, 3],
    "is_ok": true
  }
]
```

---

## Roboter-Konfiguration (Deep Dive)

Alle Roboter-Einstellungen stehen in **einer einzigen Datei**:

**`app/infrastructure/robot/robot_config.json`**

```json
{
  "robot_ip": "10.10.10.10",
  "gripper_speed": 500,

  "positions": {
    "step1":    [-0.013, 0.61, -1.267, 0.002, -0.032, 0.015],
    "step2":    [-0.781, -0.037, -0.217, -0.078, -0.5, 0.048],
    "step3":    [-0.772, -0.793, -0.148, -0.055, -0.499, 0.048],
    "step4":    [-0.775, 0.61, -0.646, 0.003, -0.025, -0.015],
    "step5":    [1.062, 0.61, -0.702, -0.001, -0.031, -0.015],
    "step6":    [0.836, -0.147, -0.839, -0.23, -0.566, -0.328],
    "step7":    [0.9109, -0.9382, -0.4416, -0.414, 1.2792, 0.0553],
    "step8":    [0.923, -0.9004, -0.4613, -0.5291, 1.0598, -2.5263],
    "step9":    [0.8835, -0.9079, -0.3658, -0.4984, 1.9097, 0.1458],
    "sort_ok":  [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "sort_nok": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
  },

  "sequence": ["step1", "step2", "step3", "step4", "step5", "step6", "step7", "step8", "step9"],

  "gripper_open_at": "step1",
  "gripper_close_at": "step3",
  "capture_at": ["step7", "step8", "step9"]
}
```

### Was bedeutet was?

| Feld | Beschreibung |
|------|-------------|
| `robot_ip` | IP-Adresse des Niryo-Roboters im Netzwerk |
| `gripper_speed` | Geschwindigkeit des Greifers (0-1000) |
| `positions` | Benannte Positionen mit 6 Gelenkwinkeln (Radiant) |
| `sequence` | Reihenfolge, in der die Positionen angefahren werden |
| `gripper_open_at` | Bei welchem Step der Greifer oeffnet |
| `gripper_close_at` | Bei welchem Step der Greifer schliesst (Wuerfel greifen) |
| `capture_at` | Bei welchen Steps die Kamera ein Bild macht (Liste!) |
| `sort_ok` | Position der "Korrekt"-Kiste (fuer Sortierung) |
| `sort_nok` | Position der "Fehlerhaft"-Kiste (fuer Sortierung) |

### Die 6 Gelenkwinkel

Jede Position besteht aus 6 Werten (Radiant), einer pro Gelenk des Niryo:

```
[Joint1, Joint2, Joint3, Joint4, Joint5, Joint6]
```

- **Joint 1**: Basis-Drehung (links/rechts)
- **Joint 2**: Schulter (vor/zurueck)
- **Joint 3**: Ellbogen (hoch/runter)
- **Joint 4**: Unterarm-Drehung
- **Joint 5**: Handgelenk (kippen)
- **Joint 6**: Handgelenk-Drehung

### Aktueller Ablauf (step1 - step9)

```
step1  → Greifer oeffnen (Startposition)
step2  → Zur Aufnahmeposition fahren
step3  → Greifer schliessen (Wuerfel greifen)
step4  → Wuerfel anheben
step5  → Wuerfel drehen / positionieren
step6  → Wuerfel vor Kamera bringen
step7  → FOTO Seite 1
step8  → FOTO Seite 2
step9  → FOTO Seite 3
Home   → Zurueck zur Ausgangsposition
        → Sortierung (sort_ok oder sort_nok)
```

---

## Neue Sequenzen einrichten

Wenn der Roboter-Ablauf fuer die finale Version angepasst werden muss, muessen **nur Aenderungen in `robot_config.json`** gemacht werden. Kein Code muss geaendert werden!

### Schritt 1: Positionen aufnehmen

Am einfachsten mit **Niryo Studio** oder dem **Learning Mode**:

1. Niryo Studio oeffnen und mit Roboter verbinden
2. Learning Mode aktivieren (Roboter von Hand fuehren)
3. Roboter manuell an die gewuenschte Position bringen
4. Joint-Werte ablesen (6 Werte in Radiant)
5. Werte notieren

Alternativ per Niryo Studio: **Joints Tab → aktuelle Werte kopieren**

### Schritt 2: robot_config.json anpassen

#### a) Neue Positionen hinzufuegen

```json
"positions": {
  "pickup":     [0.1, 0.5, -0.8, 0.0, -0.3, 0.0],
  "inspect_1":  [0.9, -0.9, -0.4, -0.4, 1.3, 0.05],
  "inspect_2":  [0.9, -0.9, -0.5, -0.5, 1.1, -2.5],
  "inspect_3":  [0.9, -0.9, -0.4, -0.5, 1.9, 0.15],
  "sort_ok":    [0.5, 0.3, -0.6, 0.0, -0.2, 0.0],
  "sort_nok":   [-0.5, 0.3, -0.6, 0.0, -0.2, 0.0]
}
```

#### b) Neue Sequenz definieren

```json
"sequence": ["pickup", "inspect_1", "inspect_2", "inspect_3"]
```

#### c) Aktionen zuordnen

```json
"gripper_close_at": "pickup",
"gripper_open_at": null,
"capture_at": ["inspect_1", "inspect_2", "inspect_3"]
```

#### d) Sortier-Positionen setzen

Die Positionen `sort_ok` und `sort_nok` MUESSEN definiert sein, damit die Sortierung funktioniert. Das sind die Positionen, an denen der Roboter den Wuerfel in die jeweilige Kiste ablegt.

```json
"sort_ok":  [0.5, 0.3, -0.6, 0.0, -0.2, 0.0],
"sort_nok": [-0.5, 0.3, -0.6, 0.0, -0.2, 0.0]
```

### Schritt 3: Testen

```bash
# Server starten
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Inspektion ausloesen
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"target_color_left": "orange", "target_color_right": "orange", "target_dots": [1, 3, 5]}'
```

### Checkliste fuer neue Sequenzen

- [ ] Alle Positionen in `positions` eingetragen (6 Joint-Werte pro Position)
- [ ] `sequence` Liste aktualisiert (Reihenfolge der Positionen)
- [ ] `gripper_close_at` gesetzt (wann Wuerfel greifen)
- [ ] `gripper_open_at` gesetzt oder `null` (wann Wuerfel loslassen, falls noetig)
- [ ] `capture_at` gesetzt (bei welchen Positionen fotografiert wird)
- [ ] `sort_ok` Position gesetzt (Kiste fuer korrekte Wuerfel)
- [ ] `sort_nok` Position gesetzt (Kiste fuer fehlerhafte Wuerfel)
- [ ] Trockentest ohne Wuerfel durchgefuehrt
- [ ] Test mit echtem Wuerfel durchgefuehrt

### Tipps

- **Positionen benennen**: Verwende sprechende Namen wie `pickup`, `inspect_1`, `sort_ok` statt `step1`, `step2`
- **Sicherheit**: Teste neue Positionen immer erst im Learning Mode
- **Kamera-Winkel**: Die Kamera sitzt am Roboter – die `capture_at`-Positionen bestimmen, aus welchem Winkel fotografiert wird
- **Dashboard nutzen**: Unter `/dashboard/` kannst du die Config auch per Web-Oberflaeche bearbeiten

---

## Installation & Start

### Voraussetzungen

- Python 3.12+
- Niryo-Roboter im Netzwerk (Standard-IP: `10.10.10.10`)
- Kamera am Roboter angeschlossen

### Installation

```bash
cd cube-inspection-system
pip install -r requirements.txt
```

### Server starten

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **API**: `http://localhost:8000`
- **Swagger-Doku**: `http://localhost:8000/docs`
- **Dashboard**: `http://localhost:8000/dashboard/`

---

## Testen

### API testen

```bash
# Systemstatus
curl http://localhost:8000/

# Healthcheck (Robot + Kamera)
curl http://localhost:8000/api/healthcheck

# Inspektion ausloesen
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"target_color_left": "orange", "target_color_right": "orange", "target_dots": [1, 3, 5]}'

# Ergebnisse abrufen
curl http://localhost:8000/api/inspections

# Roboter kalibrieren
curl -X POST http://localhost:8000/api/calibration
```

### Einzelne Module testen

```bash
# Kamera-Verbindung
python tests/test_cameraConnection.py

# Vision (Live-Stream mit Erkennung)
python tests/test_vision.py

# Roboter-Steuerung
python tests/test_robot.py

# Greifer
python tests/test_gripper.py

# API-Endpunkte
python -m pytest tests/test_api.py -v
```
