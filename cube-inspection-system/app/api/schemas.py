# API schemas
import json
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List

class ConfigurationCreate(BaseModel):
    target_color_left: str
    target_color_right: str
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
                "target_color_left": "rot",
                "target_color_right": "blau",
                "target_dots": [1, 2, 3]
            }
        }
class InspectionCreate(BaseModel):
    config_id: int
    actual_color_left: Optional[str] = None
    actual_color_right: Optional[str] = None
    actual_dots: Optional[List[int]] = None
    confidence: Optional[float] = None
    is_ok: bool

class InspectionResponse(BaseModel):
    id: int
    config_id: int
    timestamp: datetime
    actual_color_left: Optional[str]
    actual_color_right: Optional[str]
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