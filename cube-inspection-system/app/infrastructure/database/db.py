import json
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Config laden
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "db_config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

# Pfad zur Datenbank
SQLALCHEMY_DATABASE_URL = config["database_url"]

# Engine & Session-Konfiguration
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": config["check_same_thread"]})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Die Basisklasse für alle Models
Base = declarative_base()