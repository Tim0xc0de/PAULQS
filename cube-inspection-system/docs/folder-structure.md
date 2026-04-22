```
cube-inspection-system/
│
├── app/                              # Hauptanwendung
│   ├── main.py                       # Einstiegspunkt – FastAPI-App, Router-Einbindung, DB-Init
│   ├── config.py                     # Globale Konfigurationseinstellungen
│   │
│   ├── api/                          # API Layer – REST-Schnittstelle nach außen
│   │   ├── routes.py                 # API-Endpunkte (POST /config, GET /inspections, GET /healthcheck, ...)
│   │   ├── schemas.py                # Pydantic-Schemas für Request-/Response-Validierung
│   │   └── dependencies.py           # Dependency Injection (DB-Session pro Request)
│   │
│   ├── application/                  # Application Layer – Geschäftslogik / Use Cases
│   │   ├── inspection_service.py     # Kompletter Inspektionsablauf: Roboter → Kamera → Erkennung → DB
│   │   └── sorting_service.py        # Sortierlogik: Würfel in OK- oder NOK-Box ablegen
│   │
│   ├── infrastructure/               # Infrastructure Layer – Technische Anbindungen
│   │   ├── robot/                    # Roboter-Steuerung (Niryo Ned2)
│   │   │   ├── robot_controller.py   # Roboter-Klasse: connect, move, grip, release, Sequenzen
│   │   │   ├── movements.py          # Hilfsfunktionen: Positionen, Sequenzen aus Config lesen
│   │   │   └── robot_config.json     # Roboter-Konfiguration (IP, Positionen, Sequenzen, Greifer)
│   │   │
│   │   ├── vision/                   # Bildverarbeitung (OpenCV)
│   │   │   ├── camera.py             # Kamera-Aufnahme über pyniryo (get_img_compressed)
│   │   │   ├── detection.py          # Würfelerkennung: Contour-Hierarchie, Augenzählung
│   │   │   ├── image_processing.py   # Bildvorverarbeitung: HSV-Masken, Schwellwerte
│   │   │   └── captures/             # Gespeicherte Aufnahmen (raw + result pro Seite)
│   │   │
│   │   └── database/                 # Datenbankzugriff (SQLAlchemy + SQLite)
│   │       ├── db.py                 # Engine, SessionLocal, Base – DB-Verbindung
│   │       ├── db_config.json        # DB-Konfiguration (Connection-String, Thread-Settings)
│   │       ├── models.py             # ORM-Modelle: Configuration, Inspection, SystemLog
│   │       └── repository.py         # Repository-Pattern: CRUD-Operationen für alle Tabellen
│   │
│   ├── dashboard/                    # Optional: Web-Dashboard für Monitoring & Konfiguration
│   │   ├── routes.py                 # Dashboard-Endpunkte (Config laden/speichern, Historie, DB-Explorer)
│   │   └── dashboard.html            # Single-Page Dashboard (HTML/CSS/JS)
│   │
│   └── utils/                        # Querschnittsfunktionen
│       └── logger.py                 # System-Logger: schreibt in DB + Konsole
│
├── tests/                            # Testverzeichnis
│   ├── test_api.py                   # API-Integrationstests
│   ├── test_robot.py                 # Roboter-Verbindungstests
│   ├── test_gripper.py               # Greifer- und Sequenztests
│   ├── test_cameraConnection.py      # Kamera-Verbindungstests
│   ├── test_comparison.py            # Vergleichslogik-Tests
│   ├── test_detection.py             # Erkennungsalgorithmus-Tests
│   ├── test_imgProcessing.py         # Bildverarbeitungs-Tests
│   └── test_images/                  # Testbilder für Vision-Tests
│
├── docs/                             # Dokumentation
│   ├── architecture-diagrams.md      # Architekturdiagramme (Mermaid)
│   └── folder-structure.md           # Ordnerstruktur (diese Datei)
│
├── test.db                           # SQLite-Datenbank (wird automatisch erstellt)
├── requirements.txt                  # Python-Abhängigkeiten
├── README.md                         # Projektbeschreibung
├── PROJEKTPLAN.md                    # Projektplanung
└── DEPLOYMENT.md                     # Deployment-Anleitung
```
