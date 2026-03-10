import os
import cv2
from app.infrastructure.database.db import SessionLocal
from app.infrastructure.database.repository import InspectionRepository
from app.infrastructure.robot.robot_controller import RobotController
from app.infrastructure.robot.movements import get_capture_at
from app.infrastructure.vision.camera import capture
from app.infrastructure.vision.detection import detect_cube
from app.domain.models import Configuration
from app.api.schemas import InspectionCreate

# Ordner für gespeicherte Bilder
CAPTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "infrastructure", "vision", "captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)


def run_inspection(config_id: int):
    """Kompletter Ablauf: Roboter fährt → Kamera → Erkennung → DB."""
    controller = RobotController()

    try:
        # 1. Roboter-Sequenz fahren, bei capture_at Bild aufnehmen
        if not controller.connect() or not controller.prepare():
            _save(config_id, None)
            return

        img = controller.run_sequence_with_capture(
            capture_step=get_capture_at(),
            capture_fn=lambda: capture(controller.robot)
        )

        # 2. Bild analysieren
        detection = detect_cube(img) if img is not None else None

        # 3. Bild speichern (Original + mit Erkennung)
        if img is not None:
            cv2.imwrite(os.path.join(CAPTURE_DIR, "last_raw.jpg"), img)
            if detection:
                _draw_result(img, detection)
            cv2.imwrite(os.path.join(CAPTURE_DIR, "last_result.jpg"), img)

        # 4. Soll/Ist vergleichen und speichern
        _save(config_id, detection)

    except Exception as e:
        print(f"[INSPECTION] Fehler: {e}")
        _save(config_id, None)
    finally:
        controller.disconnect()


def _draw_result(img, detection):
    """Zeichnet Bounding-Box und Augenzahl ins Bild."""
    x, y, w, h = detection["x"], detection["y"], detection["w"], detection["h"]
    dots = detection["dots"]
    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.putText(img, f"Augen: {dots}", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


def _save(config_id: int, detection: dict | None):
    """Speichert das Ergebnis in der DB."""
    db = SessionLocal()
    try:
        repo = InspectionRepository(db)
        config = db.query(Configuration).filter(Configuration.id == config_id).first()

        # Erkannte Augenzahl auslesen
        actual_dots = None
        if detection:
            actual_dots = detection["dots"]

        # Soll/Ist vergleichen
        is_ok = False
        if actual_dots is not None and config:
            is_ok = actual_dots == config.target_dots

        repo.save_inspection(InspectionCreate(
            config_id=config_id,
            actual_dots=actual_dots,
            is_ok=is_ok,
        ))
        print(f"[INSPECTION] Ergebnis: Augen={actual_dots}, OK={is_ok}")
    finally:
        db.close()
