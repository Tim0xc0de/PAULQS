from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.infrastructure.database.db import SessionLocal
from app.api import schemas
from app.domain import models

# 1. Der Router muss definiert sein
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 2. Hier ist der POST-Endpunkt (den siehst du ja schon)
@router.post("/config", response_model=schemas.ConfigurationCreate)
def receive_config(config: schemas.ConfigurationCreate, db: Session = Depends(get_db)):
    new_config = models.Configuration(**config.model_dump())
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    return new_config

# 3. PRÜFE DIESEN TEIL: Hier muss @router.get stehen!
@router.get("/inspections", response_model=List[schemas.InspectionResponse])
def get_inspections(limit: int = 10, db: Session = Depends(get_db)):
    results = db.query(models.Inspection).limit(limit).all()
    return results