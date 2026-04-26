# ====================================================================
# IMPORTS
# ====================================================================
import threading
from datetime import datetime, timedelta
from app.infrastructure.database.db import SessionLocal
from app.infrastructure.database.models import SystemLog, Configuration, Inspection

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

# ====================================================================
# LOG ROTATION (Loescht Eintraege aelter als 30 Tage)
# ====================================================================
LOG_RETENTION_DAYS = 30
_rotation_timer = None

def cleanup_old_data():
    """Loescht alle Datensaetze (Logs, Inspektionen, Konfigurationen) aelter als LOG_RETENTION_DAYS Tage."""
    try:
        db = SessionLocal()
        cutoff = datetime.utcnow() - timedelta(days=LOG_RETENTION_DAYS)
        deleted_logs = db.query(SystemLog).filter(SystemLog.timestamp < cutoff).delete()
        deleted_insp = db.query(Inspection).filter(Inspection.timestamp < cutoff).delete()
        deleted_conf = db.query(Configuration).filter(Configuration.created_at < cutoff).delete()
        db.commit()
        total = deleted_logs + deleted_insp + deleted_conf
        if total:
            print(f"[LOGGER] Rotation: {deleted_logs} Logs, {deleted_insp} Inspektionen, {deleted_conf} Konfigurationen geloescht (aelter als {LOG_RETENTION_DAYS} Tage).")
    except Exception as e:
        print(f"[LOGGER] Fehler bei Rotation: {e}")
    finally:
        db.close()

def _rotation_loop():
    """Fuehrt die Log-Rotation aus und plant den naechsten Lauf in 24 Stunden."""
    global _rotation_timer
    cleanup_old_data()
    _rotation_timer = threading.Timer(86400, _rotation_loop)
    _rotation_timer.daemon = True
    _rotation_timer.start()

def start_log_rotation():
    """Startet die taegliche Log-Rotation im Hintergrund."""
    _rotation_loop()
    print(f"[LOGGER] Log-Rotation aktiv (Eintraege > {LOG_RETENTION_DAYS} Tage werden taeglich geloescht).")