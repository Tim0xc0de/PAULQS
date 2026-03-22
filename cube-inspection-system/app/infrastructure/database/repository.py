import json
from sqlalchemy.orm import Session
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
            target_dots=json.dumps(config_data.target_dots)
        )
        self.db.add(db_config)
        self.db.commit()
        self.db.refresh(db_config)
        
        # Automatisches Logging im SystemLog
        self.log_system_event("API", "INFO", f"Neue Konfiguration erstellt (ID: {db_config.id})")
        
        return db_config

    # --- Methoden für INSPECTIONS ---

    def get_all_inspections(self, limit: int = 10):
        """Holt die neuesten Prüfergebnisse."""
        return self.db.query(models.Inspection)\
            .order_by(models.Inspection.timestamp.desc())\
            .limit(limit).all()

    def save_inspection(self, inspection_data: schemas.InspectionCreate):
        """Speichert ein Prüfergebnis."""
        data = inspection_data.model_dump()
        if data.get("actual_dots") is not None:
            data["actual_dots"] = json.dumps(data["actual_dots"])
        db_inspection = models.Inspection(**data)
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