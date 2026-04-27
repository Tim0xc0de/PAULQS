# ====================================================================
# IMPORTS
# ====================================================================
import json
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List

# ====================================================================
# CONFIGURATION SCHEMAS
# ====================================================================
class ConfigurationCreate(BaseModel):
    target_color: str
    target_dots: List[int]

    @field_validator("target_dots", mode="before")
    @classmethod
    def parse_target_dots(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "target_color": "rot",
                "target_dots": [1, 2, 3, 4, 5, 6]
            }
        }

# ====================================================================
# INSPECTION SCHEMAS
# ====================================================================
class InspectionCreate(BaseModel):
    config_id: int
    actual_color: Optional[str] = None
    actual_dots: Optional[List[int]] = None
    confidence: Optional[float] = None
    is_ok: bool

class InspectionResponse(BaseModel):
    id: int
    config_id: int
    timestamp: datetime
    actual_color: Optional[str]
    actual_dots: Optional[List[int]]
    confidence: Optional[float]
    is_ok: bool

    @field_validator("actual_dots", mode="before")
    @classmethod
    def parse_dots(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    class Config:
        from_attributes = True # Erlaubt Pydantic, SQLAlchemy-Objekte zu lesen