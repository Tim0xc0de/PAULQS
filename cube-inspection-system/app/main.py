import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.infrastructure.database.db import engine, Base
from app.api.routes import router as api_router
from app.dashboard.routes import router as dashboard_router
from app.utils.logger import start_log_rotation

# 1. Datenbank-Tabellen beim Start sicherstellen
Base.metadata.create_all(bind=engine)

# 2. FastAPI App initialisieren
app = FastAPI(title="Cube Inspection API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 3. Routen einbinden
app.include_router(api_router, prefix="/api")
app.include_router(dashboard_router, prefix="/dashboard")

# 4. Log-Rotation starten (loescht Logs aelter als 30 Tage, taeglich)
@app.on_event("startup")
def on_startup():
    start_log_rotation()

@app.get("/")
def read_root():
    return {"status": "Cube Inspection System Online"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)