from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.infrastructure.database.db import SessionLocal
from app.api import schemas
from app.infrastructure.database.repository import InspectionRepository

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/config", response_model=schemas.ConfigurationCreate)
def receive_config(config: schemas.ConfigurationCreate, db: Session = Depends(get_db)):
    repo = InspectionRepository(db)
    return repo.save_config(config) 

@router.get("/inspections", response_model=List[schemas.InspectionResponse])
def get_inspections(limit: int = 10, db: Session = Depends(get_db)):
    # Auch hier: Das Repo holt die Daten
    repo = InspectionRepository(db)
    return repo.get_all_inspections(limit)