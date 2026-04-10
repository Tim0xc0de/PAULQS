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
from app.infrastructure.database import models

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


@router.get("/system-logs")
def get_system_logs(module: str = None, level: str = None, limit: int = 200, db: Session = Depends(get_db)):
    """Gibt System-Logs zurueck, optional gefiltert nach Modul und Level."""
    query = db.query(models.SystemLog).order_by(models.SystemLog.timestamp.desc())
    if module:
        query = query.filter(models.SystemLog.module == module)
    if level:
        query = query.filter(models.SystemLog.level == level)
    logs = query.limit(limit).all()
    return [
        {
            "id": log.id,
            "module": log.module,
            "level": log.level,
            "message": log.message,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in logs
    ]


@router.get("/inspection-history")
def get_inspection_history(limit: int = 30, db: Session = Depends(get_db)):
    """Gibt die letzten N Inspektionen als Liste zurück (für Historie-Grafiken)."""
    repo = InspectionRepository(db)
    inspections = repo.get_all_inspections(limit=limit)
    result = []
    for insp in reversed(inspections):
        actual_dots = json.loads(insp.actual_dots) if insp.actual_dots else None
        result.append({
            "id": insp.id,
            "timestamp": insp.timestamp.isoformat() if insp.timestamp else None,
            "is_ok": insp.is_ok,
            "actual_dots": actual_dots,
            "confidence": insp.confidence,
        })
    return result


@router.get("/db-tables")
def get_db_tables(db: Session = Depends(get_db)):
    """Gibt eine Übersicht aller Datenbank-Tabellen mit Zeilenanzahl zurück."""
    tables = []
    for model, name in [
        (models.Configuration, "configurations"),
        (models.Inspection, "inspections"),
        (models.SystemLog, "system_logs"),
    ]:
        count = db.query(model).count()
        tables.append({"name": name, "count": count})
    return tables


@router.get("/db-table/{table_name}")
def get_db_table_data(table_name: str, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """Gibt die Daten einer Tabelle zurück (paginiert)."""
    table_map = {
        "configurations": models.Configuration,
        "inspections": models.Inspection,
        "system_logs": models.SystemLog,
    }
    model = table_map.get(table_name)
    if not model:
        return JSONResponse({"error": "Tabelle nicht gefunden"}, status_code=404)

    total = db.query(model).count()
    rows = db.query(model).order_by(model.id.desc()).offset(offset).limit(limit).all()

    # Spalten aus Model extrahieren
    columns = [c.name for c in model.__table__.columns]

    data = []
    for row in rows:
        item = {}
        for col in columns:
            val = getattr(row, col)
            if hasattr(val, 'isoformat'):
                val = val.isoformat()
            item[col] = val
        data.append(item)

    return {"table": table_name, "columns": columns, "rows": data, "total": total, "limit": limit, "offset": offset}


@router.delete("/db-table/{table_name}")
def clear_db_table(table_name: str, db: Session = Depends(get_db)):
    """Löscht alle Einträge einer Tabelle."""
    table_map = {
        "configurations": models.Configuration,
        "inspections": models.Inspection,
        "system_logs": models.SystemLog,
    }
    model = table_map.get(table_name)
    if not model:
        return JSONResponse({"error": "Tabelle nicht gefunden"}, status_code=404)
    count = db.query(model).count()
    db.query(model).delete()
    db.commit()
    return {"status": "success", "deleted": count, "table": table_name}


@router.delete("/db-table/{table_name}/{row_id}")
def delete_db_row(table_name: str, row_id: int, db: Session = Depends(get_db)):
    """Löscht einen einzelnen Eintrag aus einer Tabelle."""
    table_map = {
        "configurations": models.Configuration,
        "inspections": models.Inspection,
        "system_logs": models.SystemLog,
    }
    model = table_map.get(table_name)
    if not model:
        return JSONResponse({"error": "Tabelle nicht gefunden"}, status_code=404)
    row = db.query(model).filter(model.id == row_id).first()
    if not row:
        return JSONResponse({"error": "Eintrag nicht gefunden"}, status_code=404)
    db.delete(row)
    db.commit()
    return {"status": "success", "deleted_id": row_id, "table": table_name}


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
