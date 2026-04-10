# ====================================================================
# IMPORTS
# ====================================================================
import os
import json
import cv2
from app.infrastructure.database.db import SessionLocal
from app.infrastructure.database.repository import InspectionRepository
from app.infrastructure.robot.robot_controller import RobotController
from app.infrastructure.robot.movements import get_capture_at
from app.infrastructure.vision.camera import capture
from app.infrastructure.vision.detection import detect_cube
from app.infrastructure.database.models import Configuration
from app.api.schemas import InspectionCreate
from app.application.sorting_service import sort_cube
from app.utils.logger import log

# ====================================================================
# KONFIGURATION
# ====================================================================
CAPTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "infrastructure", "vision", "captures")
os.makedirs(CAPTURE_DIR, exist_ok=True)

# ====================================================================
# INSPECTION SERVICE
# ====================================================================
def run_inspection(config_id: int):
    """Kompletter Ablauf: Roboter → Kamera → Erkennung → Vergleich → DB."""
    controller = RobotController()

    try:
        log("INSPECTION", "INFO", f"Inspektion gestartet (Config-ID: {config_id})")

        # Schritt 1: Roboter verbinden
        if not controller.connect():
            log("INSPECTION", "ERROR", "Roboter-Verbindung fehlgeschlagen")
            _save_result(config_id, [])
            return
        log("INSPECTION", "INFO", "Roboter verbunden")
        
        # Schritt 2: Roboter vorbereiten (Kalibrierung prüfen)
        if not controller.prepare():
            log("INSPECTION", "ERROR", "Roboter-Vorbereitung fehlgeschlagen (Kalibrierung?)")
            _save_result(config_id, [])
            return
        log("INSPECTION", "INFO", "Roboter vorbereitet")

        # Schritt 3: Roboter-Sequenz fahren und Bilder aufnehmen
        capture_positions = get_capture_at()
        log("INSPECTION", "INFO", f"Starte Sequenz, Fotos bei: {capture_positions}")
        captures = _run_robot_sequence(controller, capture_positions)
        log("INSPECTION", "INFO", f"Sequenz abgeschlossen, {len(captures)} Bilder aufgenommen")

        # Schritt 4: Jedes Bild analysieren
        detections = _analyze_images(captures)

        # Schritt 5: Ergebnis in Datenbank speichern
        is_ok = _save_result(config_id, detections)

        # Schritt 6: Würfel in die richtige Kiste sortieren
        sort_cube(controller, is_ok)

        log("INSPECTION", "INFO", f"Inspektion abgeschlossen (Config-ID: {config_id}, OK: {is_ok})")

    except Exception as e:
        log("INSPECTION", "ERROR", f"Unerwarteter Fehler: {e}")
        _save_result(config_id, [])
    finally:
        controller.disconnect()

# ====================================================================
# HILFSFUNKTIONEN
# ====================================================================
def _run_robot_sequence(controller, capture_positions):
    """
    Führt die Roboter-Sequenz aus und macht Fotos an bestimmten Positionen.
    
    Returns:
        Liste von (position_name, bild) Tupeln
    """
    captures = controller.run_sequence_with_capture(
        capture_steps=capture_positions,
        capture_fn=lambda: capture(controller.robot)
    )
    return captures

def _analyze_images(captures):
    """
    Analysiert alle aufgenommenen Bilder und speichert sie.
    
    Returns:
        Liste von Detektionen (kann None enthalten)
    """
    detections = []
    
    for i, (step_name, img) in enumerate(captures, start=1):
        if img is None:
            log("VISION", "WARNING", f"Seite {i} ({step_name}): Kein Bild erhalten")
            detections.append(None)
            continue
        
        # Würfel im Bild erkennen
        detection = detect_cube(img)
        detections.append(detection)
        
        # Rohbild speichern
        raw_path = os.path.join(CAPTURE_DIR, f"side_{i}_raw.jpg")
        cv2.imwrite(raw_path, img)
        
        if detection:
            log("VISION", "INFO", f"Seite {i} ({step_name}): {detection['dots']} Augen erkannt")
            # Ergebnisbild mit Box speichern
            result_img = img.copy()
            _draw_box(result_img, detection)
            result_path = os.path.join(CAPTURE_DIR, f"side_{i}_result.jpg")
            cv2.imwrite(result_path, result_img)
        else:
            log("VISION", "WARNING", f"Seite {i} ({step_name}): Kein Wuerfel erkannt")
    
    return detections

def _draw_box(img, detection):
    """Zeichnet Box und Augenzahl ins Bild."""
    x, y, w, h = detection["x"], detection["y"], detection["w"], detection["h"]
    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.putText(img, f"Augen: {detection['dots']}", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

def _save_result(config_id: int, detections: list) -> bool:
    """Speichert Ergebnis in DB und gibt is_ok zurück."""
    db = SessionLocal()
    try:
        repo = InspectionRepository(db)
        config = db.query(Configuration).filter(Configuration.id == config_id).first()

        actual_dots = [d["dots"] for d in detections if d is not None]
        target_dots = json.loads(config.target_dots) if config and config.target_dots else []

        is_ok = sorted(actual_dots) == sorted(target_dots) if actual_dots and target_dots else False

        repo.save_inspection(InspectionCreate(
            config_id=config_id,
            actual_dots=actual_dots if actual_dots else None,
            is_ok=is_ok,
        ))
        log("INSPECTION", "INFO", f"Ergebnis: Soll={target_dots}, Ist={actual_dots}, OK={is_ok}")
        return is_ok
    finally:
        db.close()
