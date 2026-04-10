# ====================================================================
# IMPORTS
# ====================================================================
from app.infrastructure.database.db import SessionLocal
from app.infrastructure.database.models import SystemLog

# ====================================================================
# SYSTEM LOGGER
# ====================================================================
def log(module: str, level: str, message: str):
    """
    Schreibt einen Eintrag in die system_logs Tabelle.
    
    Erstellt automatisch eine eigene DB-Session.
    Kann von ueberall aufgerufen werden, ohne eine Session zu uebergeben.
    
    Module:  ROBOT, VISION, INSPECTION, SORTING, API, DATABASE
    Levels:  INFO, WARNING, ERROR
    
    Beispiel:
        log("ROBOT", "INFO", "Verbindung hergestellt (10.10.10.10)")
        log("VISION", "ERROR", "Kamera nicht erreichbar")
    """
    # Auch immer in die Konsole schreiben
    print(f"[{module}] [{level}] {message}")
    
    try:
        db = SessionLocal()
        entry = SystemLog(module=module, level=level, message=message)
        db.add(entry)
        db.commit()
    except Exception as e:
        print(f"[LOGGER] Fehler beim Schreiben in DB: {e}")
    finally:
        db.close()