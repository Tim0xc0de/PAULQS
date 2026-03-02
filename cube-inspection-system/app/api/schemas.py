# API schemas
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ConfigurationCreate(BaseModel):
    target_color_left: str
    target_color_right: str
    target_dots: int

    class Config:
        json_schema_extra = {
            "example": {
                "target_color_left": "rot",
                "target_color_right": "blau",
                "target_dots": 5
            }
        }
class InspectionResponse(BaseModel):
    id: int
    config_id: int
    timestamp: datetime
    actual_color_left: Optional[str]
    actual_color_right: Optional[str]
    actual_dots: Optional[int]
    confidence: Optional[float]
    is_ok: bool

    class Config:
        from_attributes = True # Erlaubt Pydantic, SQLAlchemy-Objekte zu lesen