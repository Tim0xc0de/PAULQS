# Cube Inspection System – PAULQS

Automatisierte Qualitätsprüfung von Würfeln mit einem **Niryo-Roboterarm**, einer **Logitech-Kamera** und **Computer Vision (OpenCV)**. Der Roboter greift einen Würfel, positioniert ihn vor der Kamera, erkennt die Augenzahl und vergleicht das Ergebnis mit einer Soll-Konfiguration.

---

## Inhaltsverzeichnis

1. [Architektur](#architektur)
2. [Projektstruktur](#projektstruktur)
3. [Technologie-Stack](#technologie-stack)
4. [Module im Detail](#module-im-detail)
5. [Datenmodell](#datenmodell)
6. [API-Endpunkte](#api-endpunkte)
7. [Inspektionsablauf](#inspektionsablauf)
8. [Konfiguration](#konfiguration)
9. [Installation & Start](#installation--start)
10. [Testen](#testen)

---

## Architektur

Das System folgt einer **modularen Schichtenarchitektur** mit klarer Trennung:

```
┌─────────────────────────────────────────────┐
│                  API-Schicht                │
│              (FastAPI + Schemas)             │
├─────────────────────────────────────────────┤
│             Anwendungsschicht               │
│           (Inspection Service)              │
├──────────┬──────────┬───────────────────────┤
│  Robot   │  Vision  │      Datenbank        │
│Controller│ Camera/  │   (SQLite + SQLAlchemy)│
│ Movement │Detection │   Repository-Pattern  │
├──────────┴──────────┴───────────────────────┤
│              Domain-Modelle                 │
│     (Configuration, Inspection, SystemLog)  │
└─────────────────────────────────────────────┘
```

**Prinzipien:**
- Jedes Modul hat **eine klare Aufgabe**
- Module kommunizieren über **definierte Schnittstellen**
- Konfiguration ist **extern** (JSON-Dateien), nicht im Code
- Datenbankzugriffe laufen über ein **Repository-Pattern**

---

## Projektstruktur

```
cube-inspection-system/
├── app/
│   ├── main.py                          # FastAPI-Einstiegspunkt
│   ├── config.py                        # Globale Konfiguration
│   │
│   ├── api/                             # API-Schicht
│   │   ├── routes.py                    # REST-Endpunkte
│   │   └── schemas.py                   # Pydantic-Schemas (Request/Response)
│   │
│   ├── application/                     # Anwendungslogik
│   │   ├── inspection_service.py        # Orchestriert: Robot → Kamera → DB
│   │   ├── comparison_service.py        # Soll/Ist-Vergleich (erweiterbar)
│   │   └── workflow.py                  # Workflow-Steuerung (erweiterbar)
│   │
│   ├── domain/                          # Datenmodelle
│   │   ├── models.py                    # SQLAlchemy-Tabellen
│   │   ├── cube.py                      # Würfel-Domänenmodell (erweiterbar)
│   │   └── inspection_result.py         # Ergebnis-Modell (erweiterbar)
│   │
│   └── infrastructure/                  # Externe Systeme
│       ├── database/
│       │   ├── db.py                    # Engine + Session-Konfiguration
│       │   ├── db_config.json           # Datenbank-Verbindungsparameter
│       │   └── repository.py            # CRUD-Operationen
│       │
│       ├── robot/
│       │   ├── robot_controller.py      # Roboter-Steuerung (Klasse)
│       │   ├── movements.py             # Config-Hilfsfunktionen
│       │   ├── robot_config.json        # Positionen, Sequenz, IP
│       │   └── dashboard.html           # Demo-Dashboard (Web-UI)
│       │
│       └── vision/
│           ├── __init__.py              # Modul-Exports
│           ├── camera.py                # Bildaufnahme (1 Funktion)
│           ├── image_processing.py      # Farbmasken + Threshold
│           └── detection.py             # Würfelerkennung + Augenzählung
│
├── tests/                               # Testdateien
│   ├── test_api.py
│   ├── test_cameraConnection.py
│   ├── test_comparison.py
│   └── test_vision.py
│
├── requirements.txt
├── .env
└── test.db                              # SQLite-Datenbank
```

---

## Technologie-Stack

| Bereich | Technologie | Zweck |
|---------|-------------|-------|
| **Web-Framework** | FastAPI | REST-API, async Background-Tasks |
| **Server** | Uvicorn | ASGI-Server für FastAPI |
| **Datenbank** | SQLite + SQLAlchemy | Persistenz, ORM |
| **Validierung** | Pydantic v2 | Request/Response-Schemas |
| **Computer Vision** | OpenCV (cv2) | Bilderkennung, Farbfilter |
| **Bildverarbeitung** | NumPy | Array-Operationen für Bilder |
| **Roboter-SDK** | pyniryo | Niryo-Roboter-Steuerung |
| **Sprache** | Python 3.12+ | Type Hints, Union-Syntax |

---

## Module im Detail

### `camera.py` – Bildaufnahme

Eine einzelne Funktion. Bekommt die Roboter-Verbindung, holt das komprimierte Bild und dekodiert es.

```python
def capture(robot: NiryoRobot) -> np.ndarray | None
```

**Ablauf:** `robot.get_img_compressed()` → `np.frombuffer()` → `cv2.imdecode()` → BGR-Bild

---

### `image_processing.py` – Bildverarbeitung

Zwei Hilfsfunktionen für die Erkennung:

| Funktion | Eingabe | Ausgabe | Zweck |
|----------|---------|---------|-------|
| `get_orange_mask(img)` | BGR-Bild | Binärmaske | Filtert orange Pixel (HSV: 5–25, 100–255, 100–255) |
| `get_dark_spots(gray_roi)` | Graustufen-ROI | Binärmaske | Findet dunkle Punkte (invertierter Threshold) |

---

### `detection.py` – Würfelerkennung

Eine Funktion, die alles kombiniert:

```python
def detect_cube(img) -> dict | None
# Rückgabe: {"x": 120, "y": 80, "w": 50, "h": 50, "dots": 3}
```

**Ablauf:**
1. `get_orange_mask()` → orange Bereiche finden
2. `cv2.findContours()` → größte Kontur = Würfel
3. Prüfung: Fläche > 1000px (kein Rauschen)
4. ROI ausschneiden → `get_dark_spots()` → Konturen zählen
5. Filter: nur Konturen mit Fläche 10–300px = echte Augen

---

### `robot_controller.py` – Roboter-Steuerung

Klasse `RobotController` mit folgenden Methoden:

| Methode | Beschreibung |
|---------|-------------|
| `connect()` | Verbindet mit dem Niryo über IP aus Config |
| `disconnect()` | Trennt die Verbindung |
| `prepare()` | Prüft Kalibrierung, deaktiviert Learning-Mode |
| `move_to(name)` | Fährt zu einer benannten Position |
| `grip()` / `release()` | Greifer steuern |
| `go_home()` | Zurück zur Home-Position |
| `run_sequence_with_capture(capture_step, capture_fn)` | Fährt die Sequenz, ruft `capture_fn` bei `capture_step` auf |

---

### `movements.py` – Konfigurationszugriff

Liest `robot_config.json` und stellt Hilfsfunktionen bereit:

```python
get_robot_ip()        # → "10.10.10.10"
get_position("step3") # → [-0.772, -0.793, ...]
get_sequence()        # → ["step1", "step2", ..., "step8"]
get_gripper_close_at()# → "step3"
get_gripper_open_at() # → "step7"
get_capture_at()      # → "step8"
```

---

### `inspection_service.py` – Orchestrator

Zwei Funktionen, die den gesamten Ablauf steuern:

```python
run_inspection(config_id)  # Hauptfunktion: Robot → Kamera → Erkennung → DB
_save(config_id, detection) # Ergebnis + Soll/Ist-Vergleich → DB
```

---

### `repository.py` – Datenbankzugriff

Klasse `InspectionRepository` (Repository-Pattern):

| Methode | Beschreibung |
|---------|-------------|
| `save_config(data)` | Speichert Soll-Konfiguration |
| `save_inspection(data)` | Speichert Prüfergebnis |
| `get_all_inspections(limit)` | Holt die letzten Ergebnisse |
| `log_system_event(module, level, msg)` | Schreibt in die SystemLog-Tabelle |

---

## Datenmodell

### `configurations` – Soll-Konfiguration
| Spalte | Typ | Beschreibung |
|--------|-----|-------------|
| id | Integer (PK) | Auto-Inkrement |
| target_color_left | String | Soll-Farbe links |
| target_color_right | String | Soll-Farbe rechts |
| target_dots | Integer | Soll-Augenzahl |
| created_at | DateTime | Erstellzeitpunkt |

### `inspections` – Prüfergebnisse
| Spalte | Typ | Beschreibung |
|--------|-----|-------------|
| id | Integer (PK) | Auto-Inkrement |
| config_id | Integer (FK) | Verweis auf Configuration |
| timestamp | DateTime | Prüfzeitpunkt |
| actual_color_left | String | Erkannte Farbe links |
| actual_color_right | String | Erkannte Farbe rechts |
| actual_dots | Integer | Erkannte Augenzahl |
| confidence | Float | Erkennungssicherheit |
| is_ok | Boolean | Soll == Ist? |

### `system_logs` – Systemprotokoll
| Spalte | Typ | Beschreibung |
|--------|-----|-------------|
| id | Integer (PK) | Auto-Inkrement |
| module | String | Modul (API, ROBOT, INSPECTION) |
| level | String | Level (INFO, ERROR) |
| message | String | Nachricht |
| timestamp | DateTime | Zeitpunkt |

---

## API-Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| `GET` | `/` | Systemstatus |
| `POST` | `/api/config` | Soll-Werte senden → startet Inspektion |
| `GET` | `/api/inspections` | Prüfergebnisse abrufen |
| `GET` | `/api/healthcheck` | Robot + Kamera Status |
| `POST` | `/api/calibration` | Roboter kalibrieren |
| `GET` | `/api/robot-config` | Robot-Config lesen (Demo) |
| `PUT` | `/api/robot-config` | Robot-Config schreiben (Demo) |
| `GET` | `/dashboard` | Web-Dashboard (Demo) |

### Beispiel: Inspektion auslösen

```bash
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"target_color_left": "orange", "target_color_right": "orange", "target_dots": 3}'
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
    "timestamp": "2026-03-09T12:30:00",
    "actual_dots": 3,
    "is_ok": true
  }
]
```

---

## Inspektionsablauf

Der komplette Flow, ausgelöst durch `POST /api/config`:

```
1. API empfängt Soll-Konfiguration (JSON)
   └─ Speichert in DB-Tabelle "configurations"
   └─ Startet Background-Task: run_inspection(config_id)

2. Roboter verbinden + vorbereiten
   └─ connect() → prepare() (Kalibrierung prüfen)

3. Sequenz abfahren (step1 → step8)
   ├─ step3: Greifer schließen (Würfel greifen)
   ├─ step7: Greifer öffnen (Würfel ablegen)
   └─ step8: Kamera-Aufnahme (capture_at)

4. Bildanalyse
   ├─ capture(robot) → BGR-Bild
   ├─ get_orange_mask() → Würfel lokalisieren
   ├─ get_dark_spots() → Augen erkennen
   └─ detect_cube() → {"dots": 3, ...}

5. Soll/Ist-Vergleich
   ├─ Soll: config.target_dots (aus DB)
   ├─ Ist:  detection["dots"] (aus Erkennung)
   └─ is_ok = (Soll == Ist)

6. Ergebnis in DB speichern
   └─ Tabelle "inspections" + SystemLog
```

---

## Konfiguration

### Roboter (`robot_config.json`)

```json
{
  "robot_ip": "10.10.10.10",
  "gripper_speed": 500,
  "positions": {
    "step1": [-0.013, 0.61, -1.267, 0.002, -0.032, 0.015],
    "step2": [...]
  },
  "sequence": ["step1", "step2", ..., "step8"],
  "gripper_close_at": "step3",
  "gripper_open_at": "step7",
  "capture_at": "step8"
}
```

- **positions**: 6 Gelenkwinkel (Joint-Werte) pro Step
- **sequence**: Reihenfolge der Steps
- **gripper_close_at / gripper_open_at**: Wann Greifer zu/auf
- **capture_at**: Wann die Kamera auslöst

### Datenbank (`db_config.json`)

```json
{
  "database_url": "sqlite:///./test.db",
  "check_same_thread": false
}
```

---

## Installation & Start

### Voraussetzungen

- Python 3.12+
- Niryo-Roboter im Netzwerk (IP: `10.10.10.10`)
- Logitech-Kamera am Roboter angeschlossen

### Installation

```bash
cd cube-inspection-system
pip install -r requirements.txt
```

### Server starten

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Der Server läuft dann auf `http://localhost:8000`.
API-Dokumentation (Swagger): `http://localhost:8000/docs`

---

## Testen

### API testen (ohne Roboter)

```bash
# Healthcheck
curl http://localhost:8000/api/healthcheck

# Config senden (löst Inspektion aus)
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"target_color_left": "orange", "target_color_right": "orange", "target_dots": 3}'

# Ergebnisse prüfen
curl http://localhost:8000/api/inspections
```

### Kamera testen (Standalone)

```bash
python tests/test_cameraConnection.py
```

### Vision testen (Live-Stream mit Erkennung)

```bash
python tests/test_vision.py
```
