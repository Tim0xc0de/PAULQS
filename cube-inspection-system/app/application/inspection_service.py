import os
import json
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
        # 1. Roboter-Sequenz fahren, bei capture_steps Bilder aufnehmen
        if not controller.connect() or not controller.prepare():
            _save(config_id, [])
            return

        captures = controller.run_sequence_with_capture(
            capture_steps=get_capture_at(),
            capture_fn=lambda: capture(controller.robot)
        )

        # 2. Jedes Bild analysieren und speichern
        detections = []
        for i, (step_name, img) in enumerate(captures, start=1):
            detection = detect_cube(img) if img is not None else None
            detections.append(detection)

            if img is not None:
                cv2.imwrite(os.path.join(CAPTURE_DIR, f"side_{i}_raw.jpg"), img)
                result_img = img.copy()
                if detection:
                    _draw_result(result_img, detection)
                cv2.imwrite(os.path.join(CAPTURE_DIR, f"side_{i}_result.jpg"), result_img)

        # 3. Soll/Ist vergleichen und speichern
        _save(config_id, detections)

    except Exception as e:
        print(f"[INSPECTION] Fehler: {e}")
        _save(config_id, [])
    finally:
        controller.disconnect()


def _draw_result(img, detection):
    """Zeichnet Bounding-Box und Augenzahl ins Bild."""
    x, y, w, h = detection["x"], detection["y"], detection["w"], detection["h"]
    dots = detection["dots"]
    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.putText(img, f"Augen: {dots}", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


def _save(config_id: int, detections: list):
    """Speichert das Ergebnis in der DB. Vergleich ist reihenfolge-unabhängig."""
    db = SessionLocal()
    try:
        repo = InspectionRepository(db)
        config = db.query(Configuration).filter(Configuration.id == config_id).first()

        # Erkannte Augenzahlen auslesen
        actual_dots = [d["dots"] for d in detections if d is not None]

        # Soll-Werte aus DB laden (JSON-String → Liste)
        target_dots = []
        if config and config.target_dots:
            target_dots = json.loads(config.target_dots)

        # Vergleich: Reihenfolge egal → sortierte Listen vergleichen
        is_ok = False
        if actual_dots and target_dots:
            is_ok = sorted(actual_dots) == sorted(target_dots)

        repo.save_inspection(InspectionCreate(
            config_id=config_id,
            actual_dots=actual_dots if actual_dots else None,
            is_ok=is_ok,
        ))
        print(f"[INSPECTION] Ergebnis: Soll={target_dots}, Ist={actual_dots}, OK={is_ok}")
    finally:
        db.close()
