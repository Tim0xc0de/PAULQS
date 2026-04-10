# ====================================================================
# IMPORTS
# ====================================================================
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.infrastructure.database.db import Base

# ====================================================================
# DATABASE MODELS
# ====================================================================
class Configuration(Base):
    __tablename__ = "configurations"
    id = Column(Integer, primary_key=True, index=True)
    target_color_left = Column(String)
    target_color_right = Column(String)
    target_dots = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    inspections = relationship("Inspection", back_populates="config")

class Inspection(Base):
    __tablename__ = "inspections"
    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("configurations.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    actual_color_left = Column(String)
    actual_color_right = Column(String)
    actual_dots = Column(String)
    confidence = Column(Float)
    is_ok = Column(Boolean)
    config = relationship("Configuration", back_populates="inspections")

class SystemLog(Base):
    __tablename__ = "system_logs"
    id = Column(Integer, primary_key=True, index=True)
    module = Column(String)
    level = Column(String)
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
