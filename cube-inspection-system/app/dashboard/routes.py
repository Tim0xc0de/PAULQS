"""
Dashboard-Routen – NUR für das DEMO-Dashboard.
Nicht Teil der Kern-API. Kann komplett entfernt werden, ohne die Inspektion zu beeinflussen.
"""
import os
import json
import glob
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from app.infrastructure.database.db import SessionLocal
from app.infrastructure.database.repository import InspectionRepository
from app.infrastructure.robot.movements import CONFIG_PATH
from app.domain import models

router = APIRouter()

DASHBOARD_HTML = os.path.join(os.path.dirname(__file__), "dashboard.html")
CAPTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "infrastructure", "vision", "captures")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Dashboard-Seite ---
@router.get("/", response_class=HTMLResponse)
def show_dashboard():
    """Zeigt das Robot Config Dashboard."""
    with open(DASHBOARD_HTML, "r") as f:
        return f.read()


# --- Robot-Config lesen/schreiben ---
@router.get("/robot-config")
def get_robot_config():
    """Liest die aktuelle robot_config.json."""
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


@router.put("/robot-config")
async def save_robot_config(request: Request):
    """Speichert die robot_config.json direkt."""
    data = await request.json()
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return {"status": "success", "message": "Config gespeichert"}


# --- Inspektionsbilder (pro Seite) ---
@router.get("/side-image/{side}/{image_type}")
def get_side_image(side: int, image_type: str):
    """Gibt das Bild einer Würfelseite zurück (raw oder result)."""
    filename = f"side_{side}_{image_type}.jpg"
    filepath = os.path.join(CAPTURE_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type="image/jpeg")
    return JSONResponse({"error": "Kein Bild vorhanden"}, status_code=404)


@router.get("/last-inspection")
def get_last_inspection(db: Session = Depends(get_db)):
    """Gibt die letzte Inspektion mit Config-Daten zurück."""
    repo = InspectionRepository(db)
    inspections = repo.get_all_inspections(limit=1)
    if not inspections:
        return JSONResponse({"error": "Keine Inspektion vorhanden"}, status_code=404)

    insp = inspections[0]
    config = db.query(models.Configuration).filter(models.Configuration.id == insp.config_id).first()

    # Anzahl vorhandener Seitenbilder ermitteln
    side_images = sorted(glob.glob(os.path.join(CAPTURE_DIR, "side_*_raw.jpg")))
    side_count = len(side_images)

    # JSON-Strings aus DB parsen
    actual_dots = json.loads(insp.actual_dots) if insp.actual_dots else None
    target_dots = json.loads(config.target_dots) if config and config.target_dots else None

    return {
        "inspection": {
            "id": insp.id,
            "timestamp": insp.timestamp.isoformat() if insp.timestamp else None,
            "actual_dots": actual_dots,
            "actual_color_left": insp.actual_color_left,
            "actual_color_right": insp.actual_color_right,
            "confidence": insp.confidence,
            "is_ok": insp.is_ok,
        },
        "config": {
            "target_dots": target_dots,
            "target_color_left": config.target_color_left if config else None,
            "target_color_right": config.target_color_right if config else None,
        },
        "side_count": side_count,
    }
