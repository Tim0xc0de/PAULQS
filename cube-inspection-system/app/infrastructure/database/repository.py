from sqlalchemy.orm import Session
from app.domain.models import Inspection, SystemLog

class InspectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_inspection(self, config_id: int, color_l: str, color_r: str, dots: int, conf: float, ok: bool):
        db_record = Inspection(
            config_id=config_id,
            actual_color_left=color_l,
            actual_color_right=color_r,
            actual_dots=dots,
            confidence=conf,
            is_ok=ok
        )
        self.db.add(db_record)
        self.db.commit()
        self.db.refresh(db_record)
        return db_record

    def log_system_event(self, module: str, level: str, message: str):
        log_entry = SystemLog(module=module, level=level, message=message)
        self.db.add(log_entry)
        self.db.commit()