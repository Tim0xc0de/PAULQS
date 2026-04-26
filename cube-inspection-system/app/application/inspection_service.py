# ====================================================================
# IMPORTS
# ====================================================================
import os
import json
import cv2
from app.infrastructure.database.db import SessionLocal
from app.infrastructure.database.repository import InspectionRepository
from app.infrastructure.robot.robot_controller import RobotController, RobotSafetyError
from app.infrastructure.robot.movements import get_capture_at
from app.infrastructure.vision.camera import capture
from app.infrastructure.vision.detection import detect_cube, draw_detection
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

        # Schritt 4: Farbe aus Konfiguration laden
        db = SessionLocal()
        try:
            config = db.query(Configuration).filter(Configuration.id == config_id).first()
            cube_color = config.target_color if config and config.target_color else "orange"
        finally:
            db.close()
        log("INSPECTION", "INFO", f"Zielfarbe: {cube_color}")

        # Schritt 5: Jedes Bild analysieren
        detections = _analyze_images(captures, cube_color)

        # Schritt 6: Ergebnis in Datenbank speichern
        is_ok = _save_result(config_id, detections)

        # Schritt 7: Würfel in die richtige Kiste sortieren
        sort_cube(controller, is_ok)

        log("INSPECTION", "INFO", f"Inspektion abgeschlossen (Config-ID: {config_id}, OK: {is_ok})")

    except RobotSafetyError as e:
        # Sicherheitsproblem (Wuerfelverlust, Kollision)
        # Notfall-Stopp wurde bereits im Controller ausgeloest.
        # LED bleibt rot, Motoren bleiben aktiv, Verbindung bleibt offen.
        log("INSPECTION", "ERROR", f"Sicherheitsproblem: {e.reason}")
        _save_result(config_id, [])
        # KEIN disconnect() - LED muss rot bleiben, Motoren muessen halten!
        # force_disconnect() muss spaeter manuell aufgerufen werden.
        return

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

def _analyze_images(captures, color: str = "orange"):
    """
    Analysiert alle aufgenommenen Bilder und speichert sie.
    
    Args:
        captures: Liste von (step_name, img) Tupeln
        color: Würfelfarbe für die Erkennung (aus COLOR_RANGES)
    
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
        detection = detect_cube(img, color)
        detections.append(detection)
        
        # Rohbild speichern
        raw_path = os.path.join(CAPTURE_DIR, f"side_{i}_raw.jpg")
        cv2.imwrite(raw_path, img)
        
        if detection:
            log("VISION", "INFO", f"Seite {i} ({step_name}): {detection['dots']} Augen erkannt")
            # Ergebnisbild mit Box speichern
            result_img = img.copy()
            draw_detection(result_img, detection)
            result_path = os.path.join(CAPTURE_DIR, f"side_{i}_result.jpg")
            cv2.imwrite(result_path, result_img)
        else:
            log("VISION", "WARNING", f"Seite {i} ({step_name}): Kein Wuerfel erkannt")
    
    return detections

def _save_result(config_id: int, detections: list) -> bool:
    """Speichert Ergebnis in DB und gibt is_ok zurück."""
    db = SessionLocal()
    try:
        repo = InspectionRepository(db)
        config = db.query(Configuration).filter(Configuration.id == config_id).first()

        actual_dots = [d["dots"] for d in detections if d is not None]
        target_dots = json.loads(config.target_dots) if config and config.target_dots else []

        # Erkannte Farbe: erste gueltige Detection nehmen
        actual_color = None
        for d in detections:
            if d is not None and d.get("color"):
                actual_color = d["color"]
                break

        target_color = config.target_color if config else None

        # Soll/Ist-Vergleich: Augenzahl UND Farbe muessen stimmen
        dots_ok = sorted(actual_dots) == sorted(target_dots) if actual_dots and target_dots else False
        color_ok = actual_color == target_color if actual_color and target_color else False
        is_ok = dots_ok and color_ok

        repo.save_inspection(InspectionCreate(
            config_id=config_id,
            actual_color=actual_color,
            actual_dots=actual_dots if actual_dots else None,
            is_ok=is_ok,
        ))
        log("INSPECTION", "INFO", f"Ergebnis: Soll={target_dots}/{target_color}, Ist={actual_dots}/{actual_color}, OK={is_ok}")
        return is_ok
    finally:
        db.close()
