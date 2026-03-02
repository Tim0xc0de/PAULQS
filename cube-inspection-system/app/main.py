import uvicorn
from fastapi import FastAPI
from app.infrastructure.database.db import engine, Base
from app.api.routes import router as api_router

# 1. Datenbank-Tabellen beim Start sicherstellen
Base.metadata.create_all(bind=engine)

# 2. FastAPI App initialisieren
app = FastAPI(title="Cube Inspection API")

# 3. Die Routen einbinden
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root():
    return {"status": "Cube Inspection System Online"}

if __name__ == "__main__":
    # Startet den Server auf Port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)