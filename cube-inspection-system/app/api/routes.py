from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from pyniryo import NiryoRobot
from app.infrastructure.database.db import SessionLocal
from app.api import schemas
from app.infrastructure.database.repository import InspectionRepository
from app.infrastructure.robot.robot_controller import RobotController
from app.infrastructure.robot.movements import get_robot_ip
from app.application.inspection_service import run_inspection

ROBOT_IP = get_robot_ip()

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/config", response_model=schemas.ConfigurationCreate)
def receive_config(config: schemas.ConfigurationCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repo = InspectionRepository(db)
    result = repo.save_config(config)
    
    background_tasks.add_task(_run_inspection, result.id)
    
    return result

def _run_inspection(config_id: int):
    """Startet die komplette Inspektion im Hintergrund."""
    run_inspection(config_id)

@router.get("/inspections", response_model=List[schemas.InspectionResponse])
def get_inspections(limit: int = 10, db: Session = Depends(get_db)):
    repo = InspectionRepository(db)
    return repo.get_all_inspections(limit)

@router.get("/healthcheck")
def health_check():
    """
    Prüft den Status der Systemkomponenten:
    - Roboter-Verbindung
    - Kalibrierungsstatus
    - Kamera-Verbindung
    """
    robot_connected = _check_robot_connection()
    robot_calibrated = _check_robot_calibration()
    camera_connected = _check_camera_connection()
    
    all_ok = robot_connected and robot_calibrated and camera_connected
    
    return {
        "status": "healthy" if all_ok else "unhealthy",
        "components": {
            "robot_connected": robot_connected,
            "robot_calibrated": robot_calibrated,
            "camera_connected": camera_connected
        }
    }

@router.post("/calibration")
def calibrate_robot():
    """Führt eine automatische Kalibrierung des Roboters durch."""
    try:
        robot = NiryoRobot(ROBOT_IP)
        robot.calibrate_auto()
        robot.close_connection()
        return {"status": "success", "message": "Roboter wurde erfolgreich kalibriert"}
    except Exception as e:
        return {"status": "error", "message": f"Kalibrierung fehlgeschlagen: {str(e)}"}

def _check_robot_connection() -> bool:
    """Prüft ob Roboter erreichbar ist."""
    try:
        robot = NiryoRobot(ROBOT_IP)
        robot.close_connection()
        return True
    except Exception:
        return False

def _check_robot_calibration() -> bool:
    """Prüft ob Roboter kalibriert ist (False = braucht Kalibrierung)."""
    try:
        robot = NiryoRobot(ROBOT_IP)
        needs_calibration = robot.need_calibration()
        robot.close_connection()
        return not needs_calibration
    except Exception:
        return False

def _check_camera_connection() -> bool:
    """Prüft ob Kamera angeschlossen ist."""
    try:
        robot = NiryoRobot(ROBOT_IP)
        img_compressed = robot.get_img_compressed()
        robot.close_connection()
        return img_compressed is not None
    except Exception:
        return False