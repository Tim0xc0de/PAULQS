from sqlalchemy.orm import Session
import subprocess
import os
import threading
from app.domain import models
from app.api import schemas

class InspectionRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Methoden für CONFIGURATIONS ---

    def save_config(self, config_data: schemas.ConfigurationCreate):
        """Speichert eine neue Soll-Konfiguration."""
        db_config = models.Configuration(
            target_color_left=config_data.target_color_left,
            target_color_right=config_data.target_color_right,
            target_dots=config_data.target_dots
        )
        self.db.add(db_config)
        self.db.commit()
        self.db.refresh(db_config)
        
        # Automatisches Logging im SystemLog
        self.log_system_event("API", "INFO", f"Neue Konfiguration erstellt (ID: {db_config.id})")
        
        # Trigger: Robot zur Home-Position fahren
        self._trigger_robot_home()
        
        return db_config
    
    def _trigger_robot_home(self):
        """Startet Robot-Script im Hintergrund."""
        def run():
            script_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "tests", "test_robot.py")
            script_path = os.path.abspath(script_path)
            print(f"[TRIGGER] Robot fährt Home: {script_path}")
            subprocess.run(["python3", script_path])
        
        threading.Thread(target=run, daemon=True).start()

    # --- Methoden für INSPECTIONS ---

    def get_all_inspections(self, limit: int = 10):
        """Holt die neuesten Prüfergebnisse."""
        return self.db.query(models.Inspection)\
            .order_by(models.Inspection.timestamp.desc())\
            .limit(limit).all()

    def save_inspection(self, inspection_data):
        """Speichert ein Prüfergebnis (wird später von PAUL/OpenCV genutzt)."""
        db_inspection = models.Inspection(**inspection_data)
        self.db.add(db_inspection)
        self.db.commit()
        self.db.refresh(db_inspection)
        return db_inspection

    # --- Methoden für SYSTEM LOGS ---

    def log_system_event(self, module: str, level: str, message: str):
        """Erzeugt einen Wartungseintrag."""
        log_entry = models.SystemLog(module=module, level=level, message=message)
        self.db.add(log_entry)
        self.db.commit()